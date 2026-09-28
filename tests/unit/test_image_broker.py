import http.client

import pytest

from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import canonical_bytes
from agent_subagent_router.transport.broker import Broker
from agent_subagent_router.image_wire import validate_claude_image_request
from test_image_wire import request_fixture


def post(broker, body):
    conn = http.client.HTTPConnection("127.0.0.1", broker._server.server_port)
    conn.request(
        "POST", "/v1/messages", body=canonical_bytes(body), headers={"x-api-key": broker.capability}
    )
    response = conn.getresponse()
    status = response.status
    response.read()
    conn.close()
    return status


@pytest.mark.parametrize("tool_response", [False, True])
def test_image_guard_zero_wire_rejection_and_no_tools(tool_response):
    task, framing, body = request_fixture()
    sent = []
    exchanges = []

    def fake(path, headers, raw):
        sent.append(raw)
        return (
            200,
            {},
            canonical_bytes(
                {
                    "id": "msg_image_fake",
                    "model": "k3-256k",
                    "stop_reason": "end_turn",
                    "usage": {"output_tokens": 1},
                    "content": [
                        {"type": "tool_use", "id": "tool_fake", "name": "Read", "input": {}}
                    ]
                    if tool_response
                    else [{"type": "text", "text": "{}"}],
                }
            ),
        )

    with Broker(
        profile("worker"),
        "SYNTHETIC",
        upstream=fake,
        request_limit=1,
        wall_seconds=5,
        generation_tokens=2048,
        request_validator=lambda x: validate_claude_image_request(task, x, framing),
        allow_response_tools=False,
        on_exchange=lambda phase, data: exchanges.append((phase, data)),
    ) as broker:
        attack = canonical_bytes(body).replace(b"Review images.", b"Unsealed truth")
        from agent_subagent_router.contracts import strict_json

        assert post(broker, strict_json(attack)) == 400
        assert sent == [] and broker.observations == []
        assert post(broker, body) == (502 if tool_response else 200)
        assert len(sent) == 1
    assert [x[0] for x in exchanges] == ["request", "response"]
    assert broker.observations[0]["classification"] == (
        "TOOL_POLICY_VIOLATION" if tool_response else "IDENTITY_VERIFIED"
    )
    assert len(broker.observations[0]["input_proof"]["images"]) == 4
