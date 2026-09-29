"""Standalone one-shot Responses relay for the MiniMax image route."""

import hashlib
import http.client
import json
import os
import sys


_BASE_URL = "http://127.0.0.1:18765"
_MAX_REQUEST_BYTES = 32 * 1024 * 1024
_MAX_RESPONSE_BYTES = 32 * 1024 * 1024


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(raw):
    text = raw.decode("utf-8", "strict") if isinstance(raw, bytes) else raw
    return json.loads(
        text,
        object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid number")),
    )


def _encode(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def main():
    connection = None
    try:
        request = sys.stdin.buffer.read(_MAX_REQUEST_BYTES + 1)
        if len(request) > _MAX_REQUEST_BYTES or type(_json(request)) is not dict:
            raise ValueError("invalid request")
        if os.environ.get("OPENAI_BASE_URL") != _BASE_URL:
            raise ValueError("invalid local endpoint")
        capability = os.environ.get("IMAGE_ROUTE_CAPABILITY")
        if not capability:
            raise ValueError("missing local capability")

        connection = http.client.HTTPConnection("127.0.0.1", 18765, timeout=180)
        connection.request(
            "POST",
            "/v1/responses",
            body=request,
            headers={
                "Authorization": "Bearer " + capability,
                "Content-Type": "application/json",
            },
        )
        upstream = connection.getresponse()
        response_bytes = upstream.read(_MAX_RESPONSE_BYTES + 1)
        if upstream.status != 200 or len(response_bytes) > _MAX_RESPONSE_BYTES:
            raise ValueError("upstream response rejected")
        response = _json(response_bytes)
        if type(response) is not dict or response.get("status") != "completed":
            raise ValueError("upstream response incomplete")
        envelope = {
            "schema": "minimax-image-runtime/v1",
            "status": "completed",
            "request_sha256": hashlib.sha256(request).hexdigest(),
            "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
            "response": response,
        }
        sys.stdout.buffer.write(_encode(envelope) + b"\n")
        return 0
    except Exception:
        sys.stderr.write("MiniMax image runner failed\n")
        sys.stderr.flush()
        return 1
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
