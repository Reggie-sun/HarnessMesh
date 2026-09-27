from types import SimpleNamespace

from agent_subagent_router.api import inspect_task
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import TaskContract
from agent_subagent_router.resolver import verify
from agent_subagent_router.transport.broker import Broker
from test_transport import post, response


def test_changed_sealed_source_blocks_next_paid_request(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    target = source/'a.py'
    target.write_text('VALUE = 1\n')
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    task = TaskContract.from_dict(dict(parent_session_id='p', task_id='guard', cwd=str(source),
        explicit_root=str(source), role='explorer', goal='Read a.py.', read_paths=['a.py'],
        write_paths=[], permissions=['read'], selected_refs=[], active_documents='not_applicable',
        harness_refs=[], constitution_refs=[], skills=[], skill_roots=[], expected_evidence=['a.py'],
        backend='kimi', profile='worker', budgets=dict(wall_seconds=30, idle_seconds=30,
        request_limit=4, context_bytes=100000)))
    manifest = inspect_task(task, tmp_path/'contracts', runtime)
    sent = []

    def upstream(*args):
        sent.append(args)
        return 200, {}, response()

    with Broker(profile('worker'), 'sentinel', request_limit=4, wall_seconds=30,
                upstream=upstream, before_request=lambda: verify(manifest)) as broker:
        assert post(broker)[0] == 200
        target.write_text('VALUE = 2\n')
        status, data = post(broker)
        assert status == 409 and b'SOURCE_CHANGED' in data
        assert len(sent) == 1
        assert len(broker.observations) == 1
        assert broker.rejections == ['SOURCE_CHANGED']
        # A later host revert cannot silently revive this invalidated invocation.
        target.write_text('VALUE = 1\n')
        assert post(broker)[0] == 403
        assert len(sent) == 1
