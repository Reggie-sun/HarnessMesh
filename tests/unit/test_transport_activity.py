from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest

from agent_subagent_router.contracts import Budgets, RouterError
from agent_subagent_router.supervisor import Invocation, supervise
from agent_subagent_router.transport.broker import KimiUpstream


def test_upstream_reports_each_received_chunk_without_releasing_partial_response(monkeypatch):
    activity = []
    reads = []
    chunks = iter([b'first', b'second', b''])

    def read1(limit):
        reads.append(limit)
        # Previous chunk must have been reported before this read blocks again.
        assert len(activity) == len(reads)  # one initial header activity + previous chunks
        return next(chunks)

    response = SimpleNamespace(status=200, read1=read1,
                               getheaders=lambda: [('Content-Type', 'text/event-stream')])
    connection = SimpleNamespace(connect=lambda: None, request=lambda *a, **k: None,
                                 getresponse=lambda: response, close=lambda: None)
    monkeypatch.setattr('http.client.HTTPSConnection', lambda *a, **k: connection)
    upstream = KimiUpstream(5, on_activity=activity.append)
    status, headers, data = upstream('/v1/messages', {}, b'{}')
    assert status == 200 and data == b'firstsecond'
    assert activity == [0, 5, 6]
    assert headers == {'content-type': 'text/event-stream'}


def test_upstream_chunking_keeps_response_limit(monkeypatch):
    response = SimpleNamespace(status=200, read1=lambda limit: b'x' * limit,
                               getheaders=lambda: [])
    connection = SimpleNamespace(connect=lambda: None, request=lambda *a, **k: None,
                                 getresponse=lambda: response, close=lambda: None)
    monkeypatch.setattr('http.client.HTTPSConnection', lambda *a, **k: connection)
    with pytest.raises(RouterError, match='UPSTREAM_OUTPUT_LIMIT'):
        KimiUpstream(5, response_limit=10, on_activity=lambda _: None)('/v1/messages', {}, b'{}')


@pytest.mark.parametrize('active,expected', [(True, 'timeout'), (False, 'idle_timeout')])
def test_transport_activity_prevents_only_idle_timeout(tmp_path, active, expected):
    invocation = Invocation((sys.executable, '-c', 'import time;time.sleep(5)'),
                            Path(tmp_path), {}, b'', Budgets(.6, .2, 1, 10000, 10000))
    revoked = []
    result = supervise(invocation, last_activity=(time.monotonic if active else lambda: 0),
                       on_stop=lambda: revoked.append(True))
    assert result.reason == expected
    assert result.duration_seconds < 1.5
    assert revoked == [True]
