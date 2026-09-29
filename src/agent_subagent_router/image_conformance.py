"""Image-specific OS/native evidence; fake upstream is never visual qualification."""
from pathlib import Path

from .contracts import RouterError, canonical_bytes, strict_json
from .image_process import ImageProcessBudgets
from .image_probe import read_probe
from .image_runtime import image_runtime
from .image_seal import verify_image_seal

OS_PROBE = '''import json,os,socket
from pathlib import Path
s=Path('/proc/self/status').read_text()
def inaccessible(path):
 try:Path(path).read_bytes();return False
 except (FileNotFoundError,PermissionError):return True
checks={'non_root':os.getuid()!=0,'no_caps':'CapEff:\\t0000000000000000' in s,
 'no_new_privileges':'NoNewPrivs:\\t1' in s,'seccomp':'Seccomp:\\t2' in s,
 'apparmor':'docker-default' in Path('/proc/self/attr/current').read_text(),
 'no_project':not Path('/work').exists() and not Path('/candidate').exists(),
 'no_host_home':not Path('/home/reggie').exists(),
 'no_global_auth':inaccessible('/root/.codex/auth.json'),
 'no_docker_socket':not Path('/var/run/docker.sock').exists(),
 'private_pid':os.getppid()==1,
 'clean_env':not any(k in os.environ for k in ['OPENAI_API_KEY','ANTHROPIC_API_KEY','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY'])}
try:
 socket.create_connection(('1.1.1.1',443),timeout=.25).close();checks['network_denied']=False
except OSError:checks['network_denied']=True
try:
 Path('/opt/router/unauthorized-write').write_text('x');checks['root_readonly']=False
except OSError:checks['root_readonly']=True
Path('/tmp/image-scratch').write_text('ok');checks['private_scratch']=True
print(json.dumps(checks))
'''


def _codex_stream(task, text):
    identity = 'resp_image_offline'
    item = {'id': 'msg_image_offline', 'type': 'message', 'role': 'assistant',
        'status': 'completed', 'content': [{'type': 'output_text', 'text': text, 'annotations': []}]}
    base = {'id': identity, 'object': 'response', 'model': task['model'],
        'max_output_tokens': task['budgets']['generation_tokens'], 'status': 'in_progress', 'output': []}
    events = [ {'type': 'response.created', 'response': base},
        {'type': 'response.output_item.added', 'response_id': identity, 'output_index': 0,
         'item': dict(item, status='in_progress', content=[])},
        {'type': 'response.content_part.added', 'response_id': identity, 'item_id': item['id'],
         'output_index': 0, 'content_index': 0, 'part': {'type': 'output_text', 'text': '', 'annotations': []}},
        {'type': 'response.output_text.delta', 'response_id': identity, 'item_id': item['id'],
         'output_index': 0, 'content_index': 0, 'delta': text},
        {'type': 'response.output_text.done', 'response_id': identity, 'item_id': item['id'],
         'output_index': 0, 'content_index': 0, 'text': text},
        {'type': 'response.output_item.done', 'response_id': identity, 'output_index': 0, 'item': item},
        {'type': 'response.completed', 'response': dict(base, status='completed', output=[item],
            usage={'input_tokens': 100, 'output_tokens': 100, 'total_tokens': 200,
                   'input_tokens_details': {'cached_tokens': 0},
                   'output_tokens_details': {'reasoning_tokens': 0}})}]
    return b''.join(b'event: '+x['type'].encode()+b'\ndata: '+canonical_bytes(x)+b'\n\n' for x in events)


def _kimi_stream(task, text):
    events = [ {'type': 'message_start', 'message': {'id': 'msg_image_offline',
        'type': 'message', 'role': 'assistant', 'model': 'k3' if task['model']=='k3[1m]' else task['model'],
        'content': [], 'usage': {'input_tokens': 100, 'output_tokens': 0}}},
        {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}},
        {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': text}},
        {'type': 'content_block_stop', 'index': 0},
        {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 100}},
        {'type': 'message_stop'}]
    return b''.join(b'event: '+x['type'].encode()+b'\ndata: '+canonical_bytes(x)+b'\n\n' for x in events)


def native_conformance(store, probe_id, *, sandbox_config, cancel=None):
    probe = store.read(probe_id)
    _, rubric = read_probe(store, probe_id, probe['manifest'])
    task = verify_image_seal(Path(probe['manifest']))['task']
    sandbox, pins = image_runtime(task, sandbox_config)
    run = store.create('router-image', 'native-conformance')
    artifacts, checks = [], {}
    invocation = None
    classification = 'INCOMPLETE'
    try:
        result = sandbox.execute(('/usr/local/bin/python3', '-c', OS_PROBE),
            {'PATH': '/usr/bin:/bin', 'HOME': '/home/worker', 'TMPDIR': '/tmp'}, b'',
            ImageProcessBudgets(20, 10, 1, 65536, 65536, 2048), source=None, cancel=cancel)
        artifacts.append(store.artifact(run, 'os-stdout.json', result.stdout, media_type='application/json'))
        artifacts.append(store.artifact(run, 'os-stderr.bin', result.stderr))
        checks = strict_json(result.stdout)
        if (result.exit_code != 0 or result.reason != 'exited' or result.truncated
                or not isinstance(checks, dict) or not checks or any(v is not True for v in checks.values())):
            raise RouterError('IMAGE_OS_CONTAINMENT_UNPROVEN')
        def upstream(path, headers, body):
            if task['backend'] == 'minimax':
                response = {'id': 'minimax_image_offline', 'object': 'response', 'status': 'completed',
                    'model': task['model'], 'store': False, 'output': [{'id': 'minimax_message_offline',
                    'type': 'message', 'role': 'assistant', 'status': 'completed',
                    'content': [{'type': 'output_text', 'text': canonical_bytes(rubric).decode()}]}],
                    'usage': {'input_tokens': 100, 'output_tokens': 100, 'total_tokens': 200}}
                return 200, {'content-type': 'application/json', 'x-request-id': 'req_image_offline'}, canonical_bytes(response)
            if task['backend'] not in ('codex', 'kimi'):
                raise RouterError('IMAGE_ROUTE_MISMATCH')
            stream = _codex_stream if task['backend'] == 'codex' else _kimi_stream
            return 200, {'content-type': 'text/event-stream', 'x-request-id': 'req_image_offline'}, stream(task, canonical_bytes(rubric).decode())
        from .image_run import run_image_contract
        invocation = run_image_contract(probe['manifest'], store,
            sandbox_config=sandbox_config, probe_id=probe_id, upstream=upstream, cancel=cancel)
        if invocation['classification'] != 'ENGINEERING_NATIVE_COMPLETE':
            raise RouterError(invocation['classification'])
        classification = 'ENGINEERING_CONFORMANCE_COMPLETE'
    except (RouterError, OSError, ValueError, TypeError) as exc:
        classification = exc.code if isinstance(exc, RouterError) else 'IMAGE_LOCAL_INPUT_ERROR'
    return store.finalize(run, {'kind': 'image-native-conformance/v1', 'classification': classification,
        'probe_id': probe_id, 'pins': pins, 'backend': task['backend'], 'model': task['model'],
        'profile': task['profile'], 'effort': task['effort'], 'checks': checks,
        'native_invocation_id': invocation['invocation_id'] if invocation else None,
        'artifacts': artifacts, 'wire_requests': 0, 'provider_requests': 0,
        'source_semantic': 'NOT_EVALUATED', 'authority': 'none', 'eligible': False})


def require_conformance(store, probe, task):
    for path in sorted(store.root.glob('*/invocation-receipt.json')):
        record = store.read(path.parent.name)
        if (record.get('kind') == 'image-native-conformance/v1'
                and record.get('classification') == 'ENGINEERING_CONFORMANCE_COMPLETE'
                and record.get('probe_id') == probe['invocation_id'] and record.get('pins') == probe['pins']
                and all(record.get(k) == task[k] for k in ('backend', 'model', 'profile', 'effort'))):
            native = store.read(record['native_invocation_id'])
            if (native.get('kind') == 'image-invocation/v1'
                    and native.get('classification') == 'ENGINEERING_NATIVE_COMPLETE'
                    and native.get('pins') == probe['pins'] and native.get('container_removed') is True):
                return record
    raise RouterError('IMAGE_NATIVE_CONFORMANCE_REQUIRED')
