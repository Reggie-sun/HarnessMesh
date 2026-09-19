"""Hash-managed local entrypoints; unknown files and private receipts are preserved."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .receipts import atomic_json


def _files(source):
    return {str(path.relative_to(source/'src')): hash_bytes(path.read_bytes())
            for path in sorted((source/'src/agent_subagent_router').rglob('*.py'))}


def _managed_paths(home):
    return (home/'.local/bin/subagent', home/'.agents/skills/external-subagent',
            home/'.local/share/agent-subagent-router/installation.json')


def _check_existing(home, manifest):
    entry, skill, _ = _managed_paths(home)
    if (entry.is_symlink() or not entry.is_file()
            or hash_bytes(entry.read_bytes()) != manifest['entry_sha256']
            or not skill.is_symlink() or os.readlink(skill) != manifest['skill_target']):
        raise RouterError('INSTALLATION_DRIFT', 'managed entry changed; preserve it')
    actual = {str(p.relative_to(skill)): hash_bytes(p.read_bytes())
              for p in skill.rglob('*') if p.is_file()}
    if actual != manifest['skill_files']:
        raise RouterError('INSTALLATION_DRIFT', 'managed skill changed; preserve it')


def install(source: Path, home: Path, python: str) -> dict:
    source, home = Path(source).resolve(), Path(home).resolve()
    entry, skill, manifest_path = _managed_paths(home)
    if manifest_path.exists():
        previous = strict_json(manifest_path.read_bytes())
        _check_existing(home, previous)
    elif any(path.exists() or path.is_symlink() for path in (entry, skill)):
        raise RouterError('UNMANAGED_INSTALLATION', 'entrypoint already exists')
    files = _files(source)
    if not files:
        raise RouterError('SOURCE_MISSING')
    source_skill = source/'skills/external-subagent'
    if not (source_skill/'SKILL.md').is_file():
        raise RouterError('SOURCE_MISSING', 'parent skill')
    skill_files = {str(p.relative_to(source_skill)): hash_bytes(p.read_bytes())
                   for p in sorted(source_skill.rglob('*')) if p.is_file()}
    source_hash = hash_bytes(canonical_bytes({'source': files, 'skill': skill_files}))
    commit = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', str(source), 'status', '--porcelain', '--',
                            'src', 'skills'], capture_output=True, text=True, check=True).stdout
    share = home/'.local/share/agent-subagent-router'
    share.mkdir(parents=True, exist_ok=True)
    package_root = share/'installations'/source_hash/'src'
    installed_skill = package_root.parent/'skills/external-subagent'
    if package_root.exists():
        for relative, digest in files.items():
            if hash_bytes((package_root/relative).read_bytes()) != digest:
                raise RouterError('INSTALLATION_DRIFT', 'existing package changed')
        for relative, digest in skill_files.items():
            if hash_bytes((installed_skill/relative).read_bytes()) != digest:
                raise RouterError('INSTALLATION_DRIFT', 'existing skill changed')
    else:
        temporary = Path(tempfile.mkdtemp(prefix='.install-', dir=share))
        try:
            for relative, digest in files.items():
                target = temporary/'src'/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                content = (source/'src'/relative).read_bytes()
                if hash_bytes(content) != digest:
                    raise RouterError('SOURCE_CHANGED')
                target.write_bytes(content)
                target.chmod(0o600)
            for relative, digest in skill_files.items():
                target = temporary/'skills/external-subagent'/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                content = (source_skill/relative).read_bytes()
                if hash_bytes(content) != digest:
                    raise RouterError('SOURCE_CHANGED')
                target.write_bytes(content)
                target.chmod(0o600)
            package_root.parent.parent.mkdir(parents=True, exist_ok=True)
            temporary.rename(package_root.parent)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
    wrapper = f'''#!{python}
import hashlib,json,pathlib,sys
sys.dont_write_bytecode = True
root = pathlib.Path({str(package_root)!r})
expected = {files!r}
found = {{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*.py')}}
if found != expected:
    sys.exit('INSTALLATION_DRIFT: installed source hashes changed')
skill = pathlib.Path({str(installed_skill)!r})
skill_expected = {skill_files!r}
skill_found = {{str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest() for p in skill.rglob('*') if p.is_file()}}
if skill_found != skill_expected:
    sys.exit('INSTALLATION_DRIFT: installed Skill hashes changed')
sys.path.insert(0, str(root))
from agent_subagent_router.cli import main
sys.exit(main())
'''.encode()
    entry.parent.mkdir(parents=True, exist_ok=True)
    skill.parent.mkdir(parents=True, exist_ok=True)
    old_entry = entry.read_bytes() if manifest_path.exists() else None
    old_skill = os.readlink(skill) if manifest_path.exists() else None
    fd, tmp = tempfile.mkstemp(prefix='.subagent-', dir=entry.parent)
    pending_skill = skill.parent/f'.external-subagent-{uuid.uuid4()}'
    replaced_entry = replaced_skill = False
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(wrapper)
            stream.flush()
            os.fsync(stream.fileno())
        Path(tmp).chmod(0o700)
        pending_skill.symlink_to(installed_skill, target_is_directory=True)
        if old_entry is not None:
            _check_existing(home, previous)
        elif any(p.exists() or p.is_symlink() for p in (entry, skill)):
            raise RouterError('UNMANAGED_INSTALLATION')
        os.replace(tmp, entry)
        replaced_entry = True
        os.replace(pending_skill, skill)
        replaced_skill = True
        manifest = {'schema_version': 1, 'source': str(source), 'source_commit': commit,
                'source_dirty_at_install': bool(dirty), 'source_hash': source_hash,
                'package_root': str(package_root), 'entry': str(entry),
                'entry_sha256': hash_bytes(wrapper), 'skill_target': str(installed_skill),
                'skill_files': skill_files, 'skill_sha256': skill_files['SKILL.md']}
        atomic_json(manifest_path, manifest, exclusive=False)
        return manifest
    except Exception:
        # Restore only exact outputs from this attempted install, never unknown changes.
        if replaced_skill:
            if not skill.is_symlink() or os.readlink(skill) != str(installed_skill):
                raise RouterError('INSTALLATION_DRIFT', 'failed install saw concurrent Skill change')
            if old_skill is None:
                skill.unlink()
            else:
                pending_skill.symlink_to(old_skill, target_is_directory=True)
                os.replace(pending_skill, skill)
        if replaced_entry:
            if entry.is_symlink() or hash_bytes(entry.read_bytes()) != hash_bytes(wrapper):
                raise RouterError('INSTALLATION_DRIFT', 'failed install saw concurrent CLI change')
            if old_entry is None:
                entry.unlink()
            else:
                with open(tmp, 'xb') as stream:
                    stream.write(old_entry)
                    stream.flush()
                    os.fsync(stream.fileno())
                Path(tmp).chmod(0o700)
                os.replace(tmp, entry)
        raise
    finally:
        Path(tmp).unlink(missing_ok=True)
        pending_skill.unlink(missing_ok=True)


def rollback(home: Path):
    home = Path(home).resolve()
    entry, skill, path = _managed_paths(home)
    if not path.is_file() or path.is_symlink():
        raise RouterError('UNMANAGED_INSTALLATION')
    manifest = strict_json(path.read_bytes())
    _check_existing(home, manifest)
    entry.unlink()
    skill.unlink()
    # Keep source/package/receipts; remove only our current entrypoint ownership record.
    path.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--python', required=True)
    args = parser.parse_args()
    print(json.dumps(install(args.source, args.home, args.python), indent=2))
