from pathlib import Path

from .adapters.claude import Runtime
from .contracts import RouterError, strict_json


CLAUDE_VERSION = '2.1.277'
CLAUDE_SHA256 = '722210f05ba494d8f6df69423c4d4f2960900f7a007d0532851c7a36e375cab7'


def installed_runtime() -> Runtime:
    binary = (Path.home()/'.local/share/agent-subagent-router/runtimes'/f'claude-{CLAUDE_VERSION}'/
              'node_modules/@anthropic-ai/claude-code-linux-x64/claude')
    if not binary.is_file():
        raise RouterError('RUNTIME_MISSING', 'install the pinned runtime; no global fallback')
    return Runtime(str(binary), CLAUDE_VERSION, CLAUDE_SHA256)


def installed_sandbox(backend='kimi', config=None):
    from .permissions.docker import DockerSandbox
    if backend not in ('kimi', 'gemini'):
        raise RouterError('BACKEND_NOT_QUALIFIED')
    filename = 'sandbox.json' if backend == 'kimi' else 'gemini-sandbox.json'
    path = Path(config) if config else Path.home()/'.local/share/agent-subagent-router'/filename
    try:
        value = strict_json(path.read_bytes())
        return DockerSandbox(value['image'], value['runtime_sha256'])
    except (OSError, KeyError, TypeError) as exc:
        raise RouterError('SANDBOX_IMAGE_UNAVAILABLE', 'build the isolated pinned image first') from exc


def installed_gemini_runtime():
    from .adapters.gemini import GeminiRuntime
    try:
        value = strict_json((Path.home()/'.local/share/agent-subagent-router/gemini-runtime.json').read_bytes())
        expected = value.pop('sha256')
        runtime = GeminiRuntime(**value)
        if runtime.version != '0.60.0' or runtime.sha256 != expected:
            raise RouterError('RUNTIME_VERSION_MISMATCH')
        return runtime
    except (OSError, TypeError, KeyError) as exc:
        raise RouterError('RUNTIME_MISSING', 'install the isolated pinned Gemini runtime') from exc


def installed_backend_runtime(backend):
    if backend == 'kimi':
        return installed_runtime()
    if backend == 'gemini':
        return installed_gemini_runtime()
    raise RouterError('BACKEND_NOT_QUALIFIED')
