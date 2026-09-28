import pytest

from agent_subagent_router.contracts import RouterError, canonical_bytes
from agent_subagent_router.image_output import decode_image_claude, parse_image_text


@pytest.mark.parametrize(
    "raw",
    [
        b"[]",
        b"null",
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b"```json\n{}\n```",
        b"Answer: {}",
        b"{} {}",
        b"\xff",
    ],
)
def test_image_object_never_repairs_invalid_output(raw):
    with pytest.raises(RouterError):
        parse_image_text(raw, 1000)


def test_complete_image_terminal_preserves_raw_and_canonical():
    text = '{ "frames": [] }'
    raw = (
        canonical_bytes({"type": "result", "subtype": "success", "is_error": False, "result": text})
        + b"\n"
    )
    assert decode_image_claude(raw, 1000) == (text.encode(), b'{"frames":[]}')
    with pytest.raises(RouterError):
        decode_image_claude(raw.rstrip(), 1000)
    with pytest.raises(RouterError):
        decode_image_claude(raw + raw, 1000)


def test_image_terminal_rejects_tool_and_output_limit():
    with pytest.raises(RouterError, match="IMAGE_OUTPUT_LIMIT"):
        parse_image_text(b'{"x":12}', 3)
    tool = (
        canonical_bytes(
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}}
        )
        + b"\n"
    )
    final = (
        canonical_bytes({"type": "result", "subtype": "success", "is_error": False, "result": "{}"})
        + b"\n"
    )
    with pytest.raises(RouterError, match="TOOL_POLICY"):
        decode_image_claude(tool + final, 1000)
