"""Baked image entry: reuse the original relay and shell-free execution owner."""
try:
    from . import container_entry
except ImportError:  # Baked beside the original standalone entry in the image.
    import container_entry


IMAGE_BODY_BYTES = 32 * 1024 * 1024
IMAGE_ENVELOPE_BYTES = 48 * 1024 * 1024
_original_reader = container_entry._read_envelope


def read_image_envelope():
    value = _original_reader()
    env = value['env']
    for key, expected in {'HOME': '/home/worker', 'CODEX_HOME': '/home/worker/codex',
                          'CLAUDE_CONFIG_DIR': '/home/worker/config', 'TMPDIR': '/tmp'}.items():
        if key in env and env[key] != expected:
            raise ValueError('invalid image environment')
    if any(key in env for key in ('OPENAI_API_KEY', 'CHATGPT_AUTH_TOKEN', 'HTTP_PROXY',
                                  'HTTPS_PROXY', 'ALL_PROXY', 'CLAUDE_CODE_OAUTH_TOKEN')):
        raise ValueError('ambient authentication forbidden')
    return value


def main():
    # The wrapper is only selected after image labels are independently checked.
    # Importing it never changes the legacy project entry or its default limits.
    container_entry._MAX_ENVELOPE = IMAGE_ENVELOPE_BYTES
    container_entry._MAX_BODY = IMAGE_BODY_BYTES
    container_entry._ALLOWED_PATHS = {'/v1/responses', '/v1/messages', '/v1/messages?beta=true'}
    container_entry._read_envelope = read_image_envelope
    return container_entry.main()


if __name__ == '__main__':
    raise SystemExit(main())
