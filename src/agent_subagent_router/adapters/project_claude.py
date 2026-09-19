"""The native read-only project surface; invoked only inside qualified containment."""
from .claude import build_invocation
from ..contracts import canonical_bytes


TOOLS = ('Read', 'Glob', 'Grep')


def project_command(runtime, route, directory, capability, budgets):
    invocation = build_invocation(runtime, route, directory,
                                  'http://127.0.0.1:18765', capability, b'', budgets)
    argv = list(invocation.argv)
    argv[0] = '/opt/runtime/claude'
    argv[argv.index('--tools')+1] = ','.join(TOOLS)
    argv[argv.index('--settings')+1] = canonical_bytes({
        'disableAllHooks': True, 'enabledPlugins': {}, 'autoMemoryEnabled': False,
        'alwaysThinkingEnabled': True, 'effortLevel': route.effort}).decode()
    argv[argv.index('--setting-sources')+1] = 'project'
    argv.remove('--disable-slash-commands')
    argv += ['--allowedTools', 'Read(//work/**)', 'Glob(//work/**)', 'Grep(//work/**)']
    env = dict(invocation.env)
    env.update(HOME='/home/worker', TMPDIR='/tmp', CLAUDE_CONFIG_DIR='/home/worker/config')
    env.pop('CLAUDE_CODE_DISABLE_CLAUDE_MDS')
    return tuple(argv), env


def project_prompt(manifest, projection):
    task = manifest['task']
    return canonical_bytes({
        'role': task['role'], 'goal': task['goal'],
        'source_map': projection['source_map'],
        'required_evidence': task['expected_evidence'],
        'report_schema': {
            'findings': ['claim with its supporting source lines'],
            'proposed_changes': [],
            'evidence_refs': [{'path': 'EXACT source_map source_path (host absolute path, not /work)',
                               'sha256': 'EXACT source_map sha256',
                               'start_line': 1, 'end_line': 1}],
            'uncertainties': [], 'questions': []},
        'instructions': (
            'Read the selected source files using Read. All paths are relative to /work. '
            'Return exactly one JSON object without markdown: findings (strings), '
            'proposed_changes (objects), evidence_refs (objects with original absolute path, '
            'sha256 from source_map, start_line and end_line), uncertainties (strings), '
            'questions (strings). Cite only actual Read results; do not invent line ranges. '
            'Each evidence_refs object has exactly the keys path, sha256, start_line, end_line. '
            'The path value MUST be source_path from source_map, never execution_path or /work. '
            'Do not use Bash, Task, Agent, MCP, network or nested delegation. '
            'Do not write files or claim parent acceptance. If required evidence is unavailable, '
            'report the gap in questions. Do not answer with prose outside the JSON object.')})
