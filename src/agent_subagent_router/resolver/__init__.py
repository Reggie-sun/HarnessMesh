"""Fail-closed project input snapshots for bounded external-worker tasks."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from agent_subagent_router.contracts import RouterError, TaskContract, canonical_bytes, hash_bytes


SCHEMA_VERSION = 1
RESOLVER_VERSION = '0.1'
_INSTRUCTION_NAMES = ('AGENTS.md', 'AGENTS.override.md', 'CLAUDE.md')
_SENSITIVE_NAMES = {
    'data', 'secret', 'secrets', 'credential', 'credentials', 'private', '.ssh', '.aws', '.config',
}


@dataclass
class _Candidate:
    path: Path
    category: str
    reason: str
    budget: '_InputBudget'
    realpath: Path = field(init=False)
    data: bytes = field(init=False)
    mode: int = field(init=False)

    def __post_init__(self) -> None:
        try:
            info = self.path.lstat()
        except OSError as exc:
            raise RouterError('SOURCE_MISSING', str(self.path)) from exc
        if stat.S_ISLNK(info.st_mode):
            raise RouterError('SYMLINK_FORBIDDEN', str(self.path))
        if not stat.S_ISREG(info.st_mode):
            raise RouterError('INVALID_SOURCE', str(self.path))
        self.realpath = self.path.resolve(strict=True)
        self.budget.consume(self.path, info.st_size)
        self.data = self.path.read_bytes()
        self.mode = stat.S_IMODE(info.st_mode)


@dataclass
class _InputBudget:
    limit: int
    total: int
    counted: set[str] = field(default_factory=set)

    def consume(self, path: Path, size: int) -> None:
        key = str(path)
        if key in self.counted:
            return
        if size < 0 or self.total + size > self.limit:
            raise RouterError('CONTRACT_TOO_LARGE', f'{self.total + size} exceeds context budget')
        self.counted.add(key)
        self.total += size


def resolve(task: TaskContract, snapshot_dir: Path, transport: dict) -> dict:
    """Materialize exactly the task's permitted source closure and seal its manifest."""
    if not isinstance(task, TaskContract):
        raise RouterError('INVALID_CONTRACT', 'task must be TaskContract')
    _validate_transport(task, transport)
    _check_capabilities(task, transport)
    project = _project_identity(task)
    root = Path(project['root'])
    snapshot_root = Path(snapshot_dir).absolute()
    if snapshot_root.exists():
        raise RouterError('SNAPSHOT_EXISTS', str(snapshot_root))

    metadata_bytes = len(canonical_bytes(task.to_dict())) + len(canonical_bytes(transport))
    budget = _InputBudget(task.budgets.context_bytes, metadata_bytes)
    if budget.total > budget.limit:
        raise RouterError('CONTRACT_TOO_LARGE', 'task metadata exceeds context budget')
    candidates: list[_Candidate] = []
    scope_files = _scope_files(task, root)
    for path in scope_files:
        candidates.append(_Candidate(path, 'source', 'read_scope', budget))
    instruction_dirs = _instruction_directories(scope_files, task, root)
    observations = _instruction_observations(instruction_dirs)
    for path in _instruction_files(instruction_dirs, task.instruction_precedence):
        candidates.append(_Candidate(path, 'instruction', 'applicable_instruction', budget))
    for ref in task.selected_refs:
        path = _task_path(ref['path'], task, root)
        _reject_sensitive(path, root)
        candidate = _Candidate(path, 'accepted_ref', 'accepted_parent_ref', budget)
        if hash_bytes(candidate.data) != ref['sha256']:
            raise RouterError('STALE_ACCEPTED_REF', str(path))
        candidates.append(candidate)
    for ref in task.constitution_refs:
        path = _task_path(ref, task, root)
        _reject_sensitive(path, root)
        candidates.append(_Candidate(path, 'constitution', 'explicit_constitution_ref', budget))
    for ref in task.harness_refs:
        path = _task_path(ref, task, root)
        _reject_sensitive(path, root)
        candidates.append(_Candidate(path, 'harness', 'explicit_harness_ref', budget))
    candidates.extend(_skill_candidates(task, root, budget))

    sources = _coalesce(candidates, root)
    _validate_instruction_bindings(observations, sources)
    if _instruction_observations(instruction_dirs) != observations:
        raise RouterError('INSTRUCTION_CHANGED', 'instruction closure changed while sealing')
    _validate_expected_evidence(task, sources)
    manifest = {
        'schema_version': SCHEMA_VERSION,
        'resolver_version': RESOLVER_VERSION,
        'task': task.to_dict(),
        'transport': dict(transport),
        'project': project,
        'snapshot_root': str(snapshot_root),
        'sources': [{key: value for key, value in item.items() if not key.startswith('_')}
                    for item in sources],
        'instruction_observations': observations,
        'instruction_precedence': list(task.instruction_precedence or []),
        'harness': {'status': 'explicit' if task.harness_refs else 'none_declared',
                    'refs': list(task.harness_refs)},
    }
    manifest['seal'] = _seal(manifest)
    _write_snapshot(snapshot_root, sources, manifest)
    return manifest


def verify(manifest: dict, check_host: bool = True) -> None:
    """Validate a seal, frozen bytes, and optionally their mutable host preimages."""
    _validate_manifest(manifest)
    try:
        calculated_seal = _seal({key: value for key, value in manifest.items() if key != 'seal'})
    except (TypeError, ValueError) as exc:
        raise RouterError('INVALID_MANIFEST', 'manifest is not canonical JSON') from exc
    if manifest['seal'] != calculated_seal:
        raise RouterError('INVALID_SEAL', 'manifest hash does not bind its contents')
    task = TaskContract.from_dict(manifest['task'])
    _validate_transport(task, manifest['transport'])
    _check_capabilities(task, manifest['transport'])
    if manifest['instruction_precedence'] != list(task.instruction_precedence or []):
        raise RouterError('INVALID_MANIFEST', 'task and manifest precedence differ')
    _validate_expected_evidence(task, manifest['sources'])
    _validate_instruction_bindings(manifest['instruction_observations'], manifest['sources'])
    snapshot_root = Path(manifest['snapshot_root'])
    _verify_snapshot_tree(snapshot_root, manifest['sources'], manifest)
    for source in manifest['sources']:
        snapshot_path = _contained_snapshot_path(snapshot_root, source['snapshot_path'])
        if snapshot_path.is_symlink() or not snapshot_path.is_file():
            raise RouterError('SNAPSHOT_CHANGED', source['snapshot_path'])
        expected_mode = _snapshot_mode(source['mode'])
        info = snapshot_path.stat()
        if info.st_size != source['size'] or stat.S_IMODE(info.st_mode) != expected_mode:
            raise RouterError('SNAPSHOT_CHANGED', source['snapshot_path'])
        if hash_bytes(snapshot_path.read_bytes()) != source['sha256']:
            raise RouterError('SNAPSHOT_CHANGED', source['snapshot_path'])
        if check_host:
            _verify_host_source(source)
    if check_host:
        _verify_instruction_observations(manifest['instruction_observations'])


def _validate_transport(task: TaskContract, transport: dict) -> None:
    required = {'backend', 'profile', 'runtime', 'capabilities'}
    if not isinstance(transport, dict) or not required <= set(transport):
        raise RouterError('INVALID_TRANSPORT', 'explicit backend/profile/runtime/capabilities required')
    if transport['backend'] != task.backend or transport['profile'] != task.profile:
        raise RouterError('INVALID_TRANSPORT', 'transport does not match task route')
    if not isinstance(transport['runtime'], str) or not transport['runtime']:
        raise RouterError('INVALID_TRANSPORT', 'runtime is required')
    caps = transport['capabilities']
    if not isinstance(caps, list) or any(not isinstance(item, str) or not item for item in caps):
        raise RouterError('INVALID_TRANSPORT', 'capabilities must be a string list')


def _check_capabilities(task: TaskContract, transport: dict) -> None:
    required = set(task.required_capabilities or [])
    missing = required - set(transport['capabilities'])
    if missing:
        raise RouterError('UNSUPPORTED_REQUIRED_CAPABILITY', ','.join(sorted(missing)))


def _project_identity(task: TaskContract) -> dict:
    cwd = Path(task.cwd).resolve()
    root_text = _git(cwd, 'rev-parse', '--show-toplevel', required=False)
    if root_text is None:
        if not task.explicit_root:
            raise RouterError('ROOT_REQUIRED', 'non-Git task requires explicit_root')
        root = Path(task.explicit_root).resolve()
        if not root.is_dir() or not _is_within(cwd, root):
            raise RouterError('INVALID_ROOT', str(root))
        return {'root': str(root), 'head': None, 'gitdir': None, 'worktree': str(root),
                'is_git': False}
    root = Path(root_text).resolve()
    gitdir = Path(_git(cwd, 'rev-parse', '--git-dir'))
    if not gitdir.is_absolute():
        gitdir = cwd / gitdir
    gitdir = gitdir.resolve()
    head = _git(cwd, 'rev-parse', 'HEAD', required=False)
    superproject = _git(cwd, 'rev-parse', '--show-superproject-working-tree', required=False) or None
    superproject_root = Path(superproject).resolve() if superproject else None
    superproject_head = (_git(superproject_root, 'rev-parse', 'HEAD', required=False)
                         if superproject_root else None)
    return {'root': str(root), 'head': head, 'gitdir': str(gitdir), 'worktree': str(root),
            'is_git': True, 'superproject_root': (str(superproject_root) if superproject_root else None),
            'superproject_head': superproject_head}


def _git(cwd: Path, *args: str, required: bool = True) -> str | None:
    result = subprocess.run(['git', '-C', str(cwd), *args], text=True, capture_output=True)
    if result.returncode:
        if required:
            raise RouterError('GIT_IDENTITY_FAILED', result.stderr.strip() or str(cwd))
        return None
    return result.stdout.strip()


def _scope_files(task: TaskContract, root: Path) -> list[Path]:
    paths: list[Path] = []
    for raw in task.read_paths:
        chosen = _task_path(raw, task, root)
        if not _is_within(chosen, root):
            raise RouterError('SCOPE_ESCAPE', str(chosen))
        _reject_sensitive(chosen, root)
        if chosen.is_symlink():
            raise RouterError('SYMLINK_FORBIDDEN', str(chosen))
        if chosen.is_file():
            paths.append(chosen)
        elif chosen.is_dir():
            paths.extend(_walk_files(chosen, root, reject_sensitive=False))
        else:
            raise RouterError('SOURCE_MISSING', str(chosen))
    if not paths:
        raise RouterError('EMPTY_SCOPE', 'read scope selected no regular files')
    return sorted(set(paths), key=lambda item: str(item))


def _task_path(raw: str, task: TaskContract, root: Path) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path(task.cwd).resolve() / candidate
    candidate = candidate.absolute()
    _reject_symlink_components(candidate)
    try:
        return candidate.resolve(strict=True)
    except OSError as exc:
        raise RouterError('SOURCE_MISSING', str(candidate)) from exc


def _walk_files(directory: Path, root: Path, *, reject_sensitive: bool) -> Iterable[Path]:
    for child in sorted(directory.rglob('*')):
        if child.is_symlink():
            raise RouterError('SYMLINK_FORBIDDEN', str(child))
        if _is_sensitive(child, root):
            if reject_sensitive:
                raise RouterError('SENSITIVE_SOURCE', str(child))
            continue
        if child.is_file():
            yield child.resolve(strict=True)


def _is_sensitive(path: Path, root: Path) -> bool:
    try:
        parts = path.resolve(strict=False).relative_to(root).parts
    except ValueError:
        parts = path.parts
    name = path.name.lower()
    return (any(part == '.git' or part in _SENSITIVE_NAMES or part.startswith('.env') for part in parts)
            or name in {'credentials.json', 'credential.json'}
            or name.endswith(('.pem', '.key', '.p12', '.pfx')))


def _instruction_directories(scope_files: list[Path], task: TaskContract, root: Path) -> set[Path]:
    directories = {source.parent for source in scope_files}
    for raw in task.write_paths:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = Path(task.cwd).resolve() / candidate
        candidate = candidate.absolute()
        _reject_symlink_components(candidate)
        existing = candidate
        while not existing.exists():
            if existing == existing.parent:
                raise RouterError('SOURCE_MISSING', str(candidate))
            existing = existing.parent
        directory = existing if existing.is_dir() else existing.parent
        if not _is_within(directory, root):
            raise RouterError('SCOPE_ESCAPE', str(candidate))
        directories.add(directory.resolve())
    expanded: set[Path] = set()
    for directory in directories:
        while True:
            expanded.add(directory)
            if directory == root:
                break
            directory = directory.parent
    directory = root.parent
    while directory != directory.parent:
        expanded.add(directory)
        directory = directory.parent
    expanded.add(directory)
    return expanded


def _instruction_files(directories: Iterable[Path], precedence: list[str] | None) -> list[Path]:
    found: list[Path] = []
    for directory in directories:
        agents = [directory / name for name in _INSTRUCTION_NAMES[:2]
                  if (directory / name).is_file()]
        claude = directory / 'CLAUDE.md'
        try:
            different_formats = agents and claude.is_file() and any(
                item.read_bytes() != claude.read_bytes() for item in agents
            )
        except OSError as exc:
            raise RouterError('INSTRUCTION_CHANGED', str(directory)) from exc
        if different_formats:
            if (not precedence or not {'AGENTS.md', 'CLAUDE.md'} <= set(precedence)
                    or precedence.index('AGENTS.md') == precedence.index('CLAUDE.md')):
                raise RouterError('CONTRACT_CONFLICT', f'instruction precedence required at {directory}')
        for name in _INSTRUCTION_NAMES:
            candidate = directory / name
            if candidate.exists() or candidate.is_symlink():
                if candidate.is_symlink():
                    raise RouterError('SYMLINK_FORBIDDEN', str(candidate))
                if not candidate.is_file():
                    raise RouterError('INVALID_SOURCE', str(candidate))
                found.append(candidate.resolve(strict=True))
    return sorted(set(found), key=lambda item: str(item))


def _instruction_observations(directories: Iterable[Path]) -> list[dict]:
    observed: dict[str, dict] = {}
    for directory in directories:
        for name in _INSTRUCTION_NAMES:
            path = directory / name
            observed[str(path)] = _instruction_observation(path)
    return [observed[key] for key in sorted(observed)]


def _instruction_observation(path: Path) -> dict:
    exists = path.exists() or path.is_symlink()
    digest = None
    if exists and path.is_file() and not path.is_symlink():
        try:
            digest = hash_bytes(path.read_bytes())
        except OSError as exc:
            raise RouterError('INSTRUCTION_CHANGED', str(path)) from exc
    return {'path': str(path), 'exists': exists, 'sha256': digest}


def _skill_candidates(task: TaskContract, root: Path, budget: _InputBudget) -> list[_Candidate]:
    if not task.skills:
        return []
    roots = []
    for raw in task.skill_roots:
        candidate = Path(raw).absolute()
        _reject_symlink_components(candidate)
        roots.append(candidate.resolve())
    if not roots:
        raise RouterError('SKILL_ROOT_REQUIRED', 'selected skills need explicit skill_roots')
    result: list[_Candidate] = []
    for selection in task.skills:
        chosen = Path(selection)
        if chosen.is_absolute() or '/' in selection:
            skill_dir = _task_path(selection, task, root)
            if not any(_is_within(skill_dir, item) for item in roots):
                raise RouterError('SKILL_ESCAPE', str(skill_dir))
        else:
            matches = []
            for item in roots:
                candidate = item / selection
                if candidate.exists():
                    _reject_symlink_components(candidate)
                    if candidate.is_dir():
                        matches.append(candidate)
            if not matches:
                raise RouterError('SKILL_NOT_FOUND', selection)
            hashes = {hash_bytes((item / 'SKILL.md').read_bytes()) for item in matches
                      if (item / 'SKILL.md').is_file()}
            if len(matches) != 1 and len(hashes) > 1:
                raise RouterError('AMBIGUOUS_SKILL', selection)
            if len(matches) != 1:
                raise RouterError('AMBIGUOUS_SKILL', selection)
            skill_dir = matches[0].resolve()
        if not (skill_dir / 'SKILL.md').is_file():
            raise RouterError('INVALID_SKILL', str(skill_dir))
        for path in _walk_files(skill_dir, root, reject_sensitive=True):
            result.append(_Candidate(path, 'skill_asset', f'selected_skill:{skill_dir}', budget))
    return result


def _coalesce(candidates: list[_Candidate], root: Path) -> list[dict]:
    gathered: dict[str, dict] = {}
    for candidate in candidates:
        key = str(candidate.path)
        if key not in gathered:
            relative = _logical_relative(candidate.path, root)
            gathered[key] = {
                'path': str(candidate.path), 'realpath': str(candidate.realpath),
                'relative_path': relative, 'snapshot_path': _snapshot_path(candidate.path, root),
                'sha256': hash_bytes(candidate.data), 'size': len(candidate.data), 'mode': candidate.mode,
                'category': candidate.category, 'selection_reason': candidate.reason,
                '_data': candidate.data, '_data_size': len(candidate.data),
            }
        else:
            gathered[key]['selection_reason'] += ',' + candidate.reason
    return [gathered[key] for key in sorted(gathered)]


def _validate_expected_evidence(task: TaskContract, sources: list[dict]) -> None:
    frozen = {
        value for source in sources for value in
        (source['path'], source['realpath'], source['relative_path'], source['snapshot_path'])
    }
    missing = [item for item in task.expected_evidence if item not in frozen]
    if missing:
        raise RouterError('UNFROZEN_EVIDENCE', ','.join(missing))


def _validate_instruction_bindings(observations: list[dict], sources: list[dict]) -> None:
    for observed in observations:
        if not observed['exists']:
            continue
        matching = [source for source in sources if source['path'] == observed['path']]
        if (not isinstance(observed['sha256'], str)
                or not any(source['sha256'] == observed['sha256']
                           and (source['category'] == 'instruction'
                                or 'applicable_instruction' in source['selection_reason'].split(','))
                           for source in matching)):
            raise RouterError('INSTRUCTION_CHANGED', f"unsealed instruction {observed['path']}")


def _logical_relative(path: Path, root: Path) -> str:
    if _is_within(path, root):
        return path.relative_to(root).as_posix()
    return 'external/' + hash_bytes(str(path).encode())[:16] + '/' + path.name


def _snapshot_path(path: Path, root: Path) -> str:
    if _is_within(path, root):
        return (Path('project') / path.relative_to(root)).as_posix()
    return (Path('external') / hash_bytes(str(path).encode())[:16] / path.name).as_posix()


def _write_snapshot(snapshot_root: Path, sources: list[dict], manifest: dict) -> None:
    snapshot_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.resolver-', dir=snapshot_root.parent))
    try:
        for source in sources:
            target = _contained_snapshot_path(temporary, source['snapshot_path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source['_data'])
            target.chmod(_snapshot_mode(source['mode']))
        manifest_path = temporary / 'manifest.json'
        manifest_path.write_bytes(canonical_bytes(manifest))
        manifest_path.chmod(0o400)
        for directory in sorted((item for item in temporary.rglob('*') if item.is_dir()), reverse=True):
            directory.chmod(0o500)
        temporary.chmod(0o500)
        os.replace(temporary, snapshot_root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _seal(manifest_without_seal: dict) -> str:
    return hash_bytes(canonical_bytes(manifest_without_seal))


def _validate_manifest(manifest: dict) -> None:
    required = {'schema_version', 'resolver_version', 'task', 'transport', 'project', 'snapshot_root',
                'sources', 'instruction_observations', 'instruction_precedence', 'harness', 'seal'}
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise RouterError('INVALID_MANIFEST', 'unexpected manifest shape')
    if manifest['schema_version'] != SCHEMA_VERSION or not isinstance(manifest['seal'], str):
        raise RouterError('INVALID_MANIFEST', 'unsupported schema or seal')
    if not isinstance(manifest['snapshot_root'], str) or not Path(manifest['snapshot_root']).is_absolute():
        raise RouterError('INVALID_MANIFEST', 'snapshot_root must be absolute')
    if (not isinstance(manifest['instruction_precedence'], list)
            or any(not isinstance(item, str) for item in manifest['instruction_precedence'])):
        raise RouterError('INVALID_MANIFEST', 'invalid instruction precedence')
    project = manifest['project']
    if (not isinstance(project, dict) or not isinstance(project.get('root'), str)
            or not Path(project['root']).is_absolute() or not isinstance(project.get('is_git'), bool)):
        raise RouterError('INVALID_MANIFEST', 'invalid project identity')
    if not isinstance(manifest['task'], dict):
        raise RouterError('INVALID_MANIFEST', 'task must be an object')
    task = TaskContract.from_dict(manifest['task'])
    _validate_transport(task, manifest['transport'])
    source_keys = {'path', 'realpath', 'relative_path', 'snapshot_path', 'sha256', 'size', 'mode',
                   'category', 'selection_reason'}
    if (not isinstance(manifest['sources'], list)
            or any(not isinstance(item, dict) or set(item) != source_keys for item in manifest['sources'])):
        raise RouterError('INVALID_MANIFEST', 'invalid source metadata')
    for source in manifest['sources']:
        if (not all(isinstance(source[key], str) and source[key] for key in
                    ('path', 'realpath', 'relative_path', 'snapshot_path', 'sha256', 'category',
                     'selection_reason'))
                or len(source['sha256']) != 64
                or any(char not in '0123456789abcdef' for char in source['sha256'])
                or type(source['size']) is not int or source['size'] < 0
                or type(source['mode']) is not int or source['mode'] < 0):
            raise RouterError('INVALID_MANIFEST', 'invalid source value')
    snapshot_paths = [source['snapshot_path'] for source in manifest['sources']]
    if len(snapshot_paths) != len(set(snapshot_paths)):
        raise RouterError('INVALID_MANIFEST', 'duplicate snapshot path')
    observations = manifest['instruction_observations']
    if (not isinstance(observations, list)
            or any(not isinstance(item, dict) or set(item) != {'path', 'exists', 'sha256'}
                   or not isinstance(item['path'], str) or not Path(item['path']).is_absolute()
                   or not isinstance(item['exists'], bool)
                   or (item['exists'] and (not isinstance(item['sha256'], str)
                                           or len(item['sha256']) != 64))
                   or (not item['exists'] and item['sha256'] is not None)
                   for item in observations)):
        raise RouterError('INVALID_MANIFEST', 'invalid instruction observations')
    harness = manifest['harness']
    if (not isinstance(harness, dict) or set(harness) != {'status', 'refs'}
            or harness['status'] not in {'explicit', 'none_declared'}
            or not isinstance(harness['refs'], list)
            or any(not isinstance(item, str) for item in harness['refs'])):
        raise RouterError('INVALID_MANIFEST', 'invalid harness')


def _verify_host_source(source: dict) -> None:
    path = Path(source['path'])
    try:
        info = path.lstat()
    except OSError as exc:
        raise RouterError('SOURCE_CHANGED', str(path)) from exc
    if _path_has_symlink_component(path) or stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RouterError('SOURCE_CHANGED', str(path))
    if (stat.S_IMODE(info.st_mode) != source['mode'] or info.st_size != source['size']
            or str(path.resolve(strict=True)) != source['realpath']
            or hash_bytes(path.read_bytes()) != source['sha256']):
        raise RouterError('SOURCE_CHANGED', str(path))


def _verify_instruction_observations(observations: list[dict]) -> None:
    if not isinstance(observations, list):
        raise RouterError('INVALID_MANIFEST', 'invalid instruction observations')
    for observed in observations:
        if not isinstance(observed, dict) or set(observed) != {'path', 'exists', 'sha256'}:
            raise RouterError('INVALID_MANIFEST', 'invalid instruction observation')
        path = Path(observed['path'])
        current = _instruction_observation(path)
        if current != observed:
            raise RouterError('INSTRUCTION_CHANGED', str(path))


def _verify_snapshot_tree(snapshot_root: Path, sources: list[dict], manifest: dict) -> None:
    try:
        root_info = snapshot_root.lstat()
    except OSError as exc:
        raise RouterError('SNAPSHOT_CHANGED', str(snapshot_root)) from exc
    if (stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode)
            or stat.S_IMODE(root_info.st_mode) != 0o500):
        raise RouterError('SNAPSHOT_CHANGED', str(snapshot_root))
    expected_files = {'manifest.json'} | {source['snapshot_path'] for source in sources}
    expected_dirs = {'.'}
    for relative in expected_files:
        parent = Path(relative).parent
        while str(parent) != '.':
            expected_dirs.add(parent.as_posix())
            parent = parent.parent
    manifest_path = snapshot_root / 'manifest.json'
    if (manifest_path.is_symlink() or not manifest_path.is_file()
            or stat.S_IMODE(manifest_path.stat().st_mode) != 0o400
            or manifest_path.read_bytes() != canonical_bytes(manifest)):
        raise RouterError('SNAPSHOT_CHANGED', 'manifest.json')
    for item in snapshot_root.rglob('*'):
        relative = item.relative_to(snapshot_root).as_posix()
        if item.is_symlink():
            raise RouterError('SNAPSHOT_CHANGED', relative)
        if item.is_dir():
            if relative not in expected_dirs or stat.S_IMODE(item.stat().st_mode) != 0o500:
                raise RouterError('SNAPSHOT_CHANGED', relative)
        elif not item.is_file() or relative not in expected_files:
            raise RouterError('SNAPSHOT_CHANGED', relative)


def _snapshot_mode(source_mode: int) -> int:
    return (source_mode & 0o500) | 0o400


def _contained_snapshot_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise RouterError('INVALID_MANIFEST', 'snapshot path escapes root')
    target = root / path
    if not _is_within(target, root):
        raise RouterError('INVALID_MANIFEST', 'snapshot path escapes root')
    return target


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _reject_sensitive(path: Path, root: Path) -> None:
    if _is_sensitive(path, root):
        raise RouterError('SENSITIVE_SOURCE', str(path))


def _reject_symlink_components(path: Path) -> None:
    """Do not normalize an input through a symlink before it has been rejected."""
    current = path
    while current != current.parent:
        if current.is_symlink():
            raise RouterError('SYMLINK_FORBIDDEN', str(current))
        current = current.parent


def _path_has_symlink_component(path: Path) -> bool:
    current = path
    while current != current.parent:
        if current.is_symlink():
            return True
        current = current.parent
    return False
