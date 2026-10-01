"""Baked native app-server driver; network belongs to the fixed local broker."""
import base64
import json
import os
import queue
import subprocess
import sys
import threading
import time

try:
    from .codex_image_rpc import DISABLED_FEATURES
except ImportError:  # Standalone baked helper, no mutable host package import.
    from codex_image_rpc import DISABLED_FEATURES


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate native key')
        result[key] = value
    return result


def _json(raw):
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))


def argv_for(task):
    argv = ['/opt/runtime/codex', 'app-server', '--enable', 'skip_host_skill_discovery']
    for feature in DISABLED_FEATURES:
        argv.extend(['--disable', feature])
    config = {
        'model_provider': '"sealed_image"', 'model': json.dumps(task['model']),
        'model_providers.sealed_image.name': '"sealed_image"',
        'model_providers.sealed_image.base_url': '"http://127.0.0.1:18765/v1"',
        'model_providers.sealed_image.env_key': '"IMAGE_ROUTE_CAPABILITY"',
        'model_providers.sealed_image.wire_api': '"responses"',
        'model_providers.sealed_image.request_max_retries': '0',
        'model_providers.sealed_image.stream_max_retries': '0',
        'orchestrator.skills.enabled': 'false', 'orchestrator.mcp.enabled': 'false',
        'agents.enabled': 'false',
        'skills.include_instructions': 'false', 'include_environment_context': 'false',
        'include_permissions_instructions': 'false', 'include_apps_instructions': 'false',
        'include_collaboration_mode_instructions': 'false',
        'tools.experimental_request_user_input.enabled': 'false',
        'tools.update_plan.enabled': 'false', 'web_search': '"disabled"',
        'approval_policy': '"never"', 'sandbox_mode': '"read-only"',
        'project_doc_max_bytes': '0', 'mcp_servers': '{}',
        'shell_environment_policy.inherit': '"none"',
        'suppress_unstable_features_warning': 'true',
    }
    for key, value in config.items():
        argv.extend(['-c', key + '=' + value])
    return argv


def main():
    process = None
    observations = []
    thread_id = turn_id = None
    error = None
    cleanup = False
    try:
        raw = sys.stdin.buffer.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024:
            raise ValueError('input limit')
        task = _json(raw)
        if set(task) != {'model', 'effort', 'system_text', 'task_text', 'png_b64',
                         'wall_seconds', 'output_bytes'}:
            raise ValueError('invalid image task')
        if (type(task['wall_seconds']) not in (float, int) or not 0 < task['wall_seconds'] <= 3600
                or type(task['output_bytes']) is not int or not 0 < task['output_bytes'] <= 8 * 1024 * 1024
                or not isinstance(task['png_b64'], list) or not 1 <= len(task['png_b64']) <= 1024):
            raise ValueError('invalid image limits')
        for image in task['png_b64']:
            if not base64.b64decode(image, validate=True).startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('invalid image')
        env = {'PATH': '/usr/bin:/bin', 'HOME': '/home/worker',
               'CODEX_HOME': '/home/worker/codex', 'TMPDIR': '/tmp', 'LANG': 'C.UTF-8',
               'IMAGE_ROUTE_CAPABILITY': os.environ['IMAGE_ROUTE_CAPABILITY']}
        os.makedirs(env['CODEX_HOME'], mode=0o700, exist_ok=False)
        process = subprocess.Popen(argv_for(task), env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        events = queue.Queue(maxsize=128)
        deadline = time.monotonic() + task['wall_seconds']

        def read():
            observed = 0
            try:
                while True:
                    line = process.stdout.readline(task['output_bytes'] + 1)
                    if not line:
                        break
                    observed += len(line)
                    if observed > task['output_bytes'] or not line.endswith(b'\n'):
                        raise ValueError('native output limit')
                    events.put(_json(line), timeout=1)
            except Exception:
                try:
                    events.put({'native_driver_error': 'INVALID_NATIVE_STREAM'}, timeout=1)
                except queue.Full:
                    pass

        def stderr():
            # The outer supervisor drains and bounds stderr independently.
            while True:
                chunk = process.stderr.read1(4096)
                if not chunk:
                    return
                sys.stderr.buffer.write(chunk)
                sys.stderr.buffer.flush()

        threading.Thread(target=read, daemon=True).start()
        threading.Thread(target=stderr, daemon=True).start()

        def send(identifier, method, params=None):
            item = {'method': method}
            if identifier is not None:
                item['id'] = identifier
            if params is not None:
                item['params'] = params
            process.stdin.write(json.dumps(item).encode() + b'\n')
            process.stdin.flush()

        def receive():
            item = events.get(timeout=max(.001, deadline - time.monotonic()))
            if not isinstance(item, dict) or 'native_driver_error' in item:
                raise ValueError('invalid native output')
            if 'method' in item and 'id' in item:
                raise ValueError('native tool request')
            observations.append(item)
            return item

        def response(identifier):
            while time.monotonic() < deadline:
                item = receive()
                if item.get('id') == identifier:
                    if 'error' in item:
                        raise ValueError('native request failed')
                    return item['result']
            raise TimeoutError()

        send(1, 'initialize', {'clientInfo': {'name': 'sealed_image', 'version': '1'},
                               'capabilities': {'experimentalApi': True}})
        response(1)
        send(None, 'initialized')
        send(2, 'thread/start', {'model': task['model'], 'modelProvider': 'sealed_image',
            'cwd': '/home/worker', 'ephemeral': True, 'approvalPolicy': 'never',
            'sandbox': 'read-only', 'environments': [], 'baseInstructions': task['system_text'],
            'developerInstructions': '', 'dynamicTools': [], 'runtimeWorkspaceRoots': [],
            'selectedCapabilityRoots': []})
        thread_id = response(2)['thread']['id']
        send(3, 'turn/start', {'threadId': thread_id,
            'input': [{'type': 'text', 'text': task['task_text']}] + [
                {'type': 'image', 'url': 'data:image/png;base64,' + png, 'detail': 'high'}
                for png in task['png_b64']],
            'environments': [], 'approvalPolicy': 'never', 'effort': task['effort'],
            'sandboxPolicy': {'type': 'readOnly', 'networkAccess': False}})
        turn_id = response(3)['turn']['id']
        while not any(item.get('method') == 'turn/completed' for item in observations):
            if time.monotonic() >= deadline:
                raise TimeoutError()
            receive()
    except Exception as exc:
        error = type(exc).__name__
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            cleanup = process.poll() is not None
        print(json.dumps({'schema': 'image-codex-native/v1', 'thread_id': thread_id,
                          'turn_id': turn_id, 'rpc': observations, 'error': error,
                          'native_cleanup': cleanup}))
    return 0 if error is None and cleanup else 1


if __name__ == '__main__':
    raise SystemExit(main())
