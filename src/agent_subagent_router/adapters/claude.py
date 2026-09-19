from dataclasses import dataclass
from pathlib import Path
import subprocess

from ..contracts import Budgets, RouterError, canonical_bytes, hash_bytes
from ..supervisor import Invocation


@dataclass(frozen=True)
class Runtime:
    executable: str
    version: str
    sha256: str

    def verify(self):
        path = Path(self.executable)
        if (not path.is_absolute() or not path.is_file() or path.is_symlink()
                or hash_bytes(path.read_bytes()) != self.sha256):
            raise RouterError('RUNTIME_CHANGED')
        result = subprocess.run([self.executable, '--version'], capture_output=True, timeout=5,
                                env={'PATH': '/usr/bin:/bin'}, close_fds=True)
        if result.returncode or result.stdout.decode().strip() != f'{self.version} (Claude Code)':
            raise RouterError('RUNTIME_VERSION_MISMATCH')

    def to_dict(self):
        return {'executable': self.executable, 'version': self.version, 'sha256': self.sha256}


def build_invocation(runtime: Runtime, profile, directory: Path, broker_url: str,
                     capability: str, prompt: bytes, budgets: Budgets) -> Invocation:
    """M1 trusted CLI, no tools, no project/native document loading."""
    runtime.verify()
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in ('home', 'config', 'cwd', 'tmp'):
        (directory/name).mkdir(mode=0o700)
    settings = directory/'settings.json'
    settings.write_bytes(canonical_bytes({'disableAllHooks': True, 'enabledPlugins': {},
                        'autoMemoryEnabled': False, 'alwaysThinkingEnabled': True,
                        'effortLevel': profile.effort}))
    settings.chmod(0o600)
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(directory/'home'),
           'TMPDIR': str(directory/'tmp'), 'LANG': 'C.UTF-8',
           'CLAUDE_CONFIG_DIR': str(directory/'config'),
           'ANTHROPIC_BASE_URL': broker_url, 'ANTHROPIC_API_KEY': capability,
           'ANTHROPIC_MODEL': profile.client_model, 'ANTHROPIC_SMALL_FAST_MODEL': profile.client_model,
           'CLAUDE_CODE_SUBAGENT_MODEL': profile.client_model,
           'CLAUDE_CODE_EFFORT_LEVEL': profile.effort, 'CLAUDE_CODE_ALWAYS_ENABLE_EFFORT': '1',
           'CLAUDE_CODE_AUTO_COMPACT_WINDOW': str(profile.context_tokens),
           'CLAUDE_CODE_MAX_CONTEXT_TOKENS': str(profile.context_tokens),
           'CLAUDE_CODE_DISABLE_AUTO_MEMORY': '1', 'CLAUDE_CODE_DISABLE_CLAUDE_MDS': '1',
           'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'DISABLE_AUTOUPDATER': '1',
           'DISABLE_TELEMETRY': '1', 'DISABLE_ERROR_REPORTING': '1',
           'MAX_THINKING_TOKENS': '8192', 'CLAUDE_CODE_MAX_RETRIES': '0'}
    for tier in ('OPUS', 'SONNET', 'HAIKU', 'FABLE'):
        env[f'ANTHROPIC_DEFAULT_{tier}_MODEL'] = profile.client_model
    argv = (runtime.executable, '-p', '--verbose', '--output-format', 'stream-json',
            '--model', profile.client_model, '--effort', profile.effort, '--tools', '',
            '--permission-mode', 'dontAsk', '--setting-sources', '', '--settings', str(settings),
            '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
            '--no-session-persistence', '--disable-slash-commands', '--no-chrome')
    return Invocation(argv, directory/'cwd', env, prompt, budgets)
