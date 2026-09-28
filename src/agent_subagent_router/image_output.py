"""Independent strict JSON object output, never project report normalization."""

from .contracts import RouterError, canonical_bytes, strict_json


def parse_image_text(raw: bytes, maximum: int) -> tuple[dict, bytes]:
    if len(raw) > maximum:
        raise RouterError("IMAGE_OUTPUT_LIMIT")
    value = strict_json(raw)
    if not isinstance(value, dict):
        raise RouterError("IMAGE_OUTPUT_PROTOCOL_ERROR")
    canonical = canonical_bytes(value)
    if len(canonical) > maximum:
        raise RouterError("IMAGE_OUTPUT_LIMIT")
    return value, canonical


def decode_image_claude(stdout: bytes, maximum: int) -> tuple[bytes, bytes]:
    if not stdout or not stdout.endswith(b"\n"):
        raise RouterError("IMAGE_TERMINAL_MISSING")
    events = [strict_json(line) for line in stdout.splitlines() if line.strip()]
    if any(not isinstance(item, dict) for item in events):
        raise RouterError("IMAGE_OUTPUT_PROTOCOL_ERROR")
    for item in events:
        if item.get("subtype") == "init":
            if (
                item.get("tools") != []
                or item.get("mcp_servers") != []
                or item.get("plugins") != []
            ):
                raise RouterError("TOOL_POLICY_VIOLATION")
        for block in item.get("message", {}).get("content", []):
            if block.get("type") in ("tool_use", "server_tool_use"):
                raise RouterError("TOOL_POLICY_VIOLATION")
    terminals = [item for item in events if item.get("type") == "result"]
    if len(terminals) != 1 or events[-1] is not terminals[0]:
        raise RouterError("IMAGE_TERMINAL_MISSING")
    terminal = terminals[0]
    if (
        terminal.get("is_error") is not False
        or terminal.get("subtype") != "success"
        or not isinstance(terminal.get("result"), str)
    ):
        raise RouterError("IMAGE_OUTPUT_PROTOCOL_ERROR")
    raw = terminal["result"].encode("utf-8")
    _, canonical = parse_image_text(raw, maximum)
    return raw, canonical
