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
    if budgets.generation_tokens is not None:
        env['CLAUDE_CODE_MAX_OUTPUT_TOKENS'] = str(budgets.generation_tokens)
    env.update(HOME='/home/worker', TMPDIR='/tmp', CLAUDE_CONFIG_DIR='/home/worker/config')
    env.pop('CLAUDE_CODE_DISABLE_CLAUDE_MDS')
    return tuple(argv), env


def project_prompt(manifest, projection):
    task = manifest['task']
    return canonical_bytes({
        'role': task['role'], 'goal': task['goal'],
        'source_map': projection['source_map'],
        'read_targets': [{'file_path': '/work/' + item['execution_path'],
                          'source_path': item['source_path']}
                         for item in projection['source_map']],
        'required_evidence': task['expected_evidence'],
        'budgets': task['budgets'],
        'report_schema': {
            'findings': ['claim with its supporting source lines'],
            'proposed_changes': [],
            'evidence_refs': [{'path': 'EXACT source_map source_path (host absolute path, not /work)',
                               'sha256': 'EXACT source_map sha256',
                               'start_line': 1, 'end_line': 1}],
            'uncertainties': [], 'questions': []},
        'instructions': (
            'Read selected files using Read with read_targets.file_path (/work paths). '
            'Never pass source_path to Read: it is a host citation identity, not a tool path. '
            'Host paths in the task or documents must be mapped through read_targets before tools. '
            'Do not retry denied host paths or bypass permissions with another tool. '
            'Batch independent necessary Reads and prioritize required_evidence. '
            'Observe HarnessMesh budget notices; FINAL_REPORT ends tool exploration. '
            'Return exactly one JSON object without markdown: findings (strings), '
            'proposed_changes (objects), evidence_refs (objects with original absolute path, '
            'sha256 from source_map, start_line and end_line), uncertainties (strings), '
            'questions (strings). Cite only actual Read results; do not invent line ranges. '
            'Each evidence_refs object has exactly the keys path, sha256, start_line, end_line. '
            'The path value MUST be source_path from source_map, never execution_path or /work. '
            'Do not use Bash, Task, Agent, MCP, network or nested delegation. '
            'Do not write files or claim parent acceptance. If required evidence is unavailable, '
            'report the gap in questions. Do not answer with prose outside the JSON object.')})
