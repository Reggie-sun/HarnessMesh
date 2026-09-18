"""Provider-neutral authority and serialization boundary; no business acceptance."""
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math
from typing import Any


class RouterError(Exception):
    def __init__(self, code: str, detail: str = ''):
        self.code = code
        self.detail = detail
        super().__init__(f'{code}: {detail}' if detail else code)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def strict_json(raw: str | bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RouterError('PROTOCOL_ERROR', 'duplicate JSON key')
            result[key] = value
        return result

    def constant(_):
        raise RouterError('PROTOCOL_ERROR', 'non-finite JSON number')

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError) as exc:
        raise RouterError('PROTOCOL_ERROR', 'invalid JSON') from exc


@dataclass(frozen=True)
class Budgets:
    wall_seconds: float
    idle_seconds: float
    request_limit: int
    output_bytes: int
    context_bytes: int

    def __post_init__(self):
        limits = {'wall_seconds': 3600, 'idle_seconds': 3600, 'request_limit': 64,
                  'output_bytes': 16 * 1024 * 1024, 'context_bytes': 8 * 1024 * 1024}
        for name, maximum in limits.items():
            value = getattr(self, name)
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or not 0 < value <= maximum):
                raise RouterError('INVALID_CONTRACT', f'invalid budget {name}')
            if name.endswith(('limit', 'bytes')) and type(value) is not int:
                raise RouterError('INVALID_CONTRACT', f'{name} must be integer')
        if self.idle_seconds > self.wall_seconds:
            raise RouterError('INVALID_CONTRACT', 'idle exceeds wall budget')


@dataclass(frozen=True)
class TaskContract:
    parent_session_id: str
    task_id: str
    cwd: str
    role: str
    goal: str
    read_paths: list[str]
    write_paths: list[str]
    permissions: list[str]
    selected_refs: list[dict]
    active_documents: str
    harness_refs: list[str]
    constitution_refs: list[str]
    skills: list[str]
    skill_roots: list[str]
    expected_evidence: list[str]
    backend: str
    profile: str
    budgets: Budgets
    explicit_root: str | None = None
    instruction_precedence: list[str] | None = None
    required_capabilities: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> 'TaskContract':
        if not isinstance(data, dict):
            raise RouterError('INVALID_CONTRACT', 'task must be an object')
        try:
            value = dict(data)
            value['budgets'] = Budgets(**value['budgets'])
            return cls(**value)
        except (TypeError, KeyError) as exc:
            raise RouterError('INVALID_CONTRACT', 'missing or unknown task fields') from exc

    def __post_init__(self):
        for name in ('parent_session_id', 'task_id', 'cwd', 'goal', 'backend', 'profile'):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise RouterError('INVALID_CONTRACT', f'{name} is required')
        if self.role not in ('explorer', 'reviewer', 'test-investigator', 'implementer'):
            raise RouterError('INVALID_CONTRACT', 'unknown role')
        for name in ('read_paths', 'write_paths', 'permissions', 'harness_refs',
                     'constitution_refs', 'skills', 'skill_roots', 'expected_evidence'):
            value = getattr(self, name)
            if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
                raise RouterError('INVALID_CONTRACT', f'invalid {name}')
            if len(set(value)) != len(value):
                raise RouterError('INVALID_CONTRACT', f'duplicate {name}')
        allowed = {'read', 'candidate-write'} if self.role == 'implementer' else {'read'}
        if set(self.permissions) - allowed or (self.role != 'implementer' and self.write_paths):
            raise RouterError('AUTHORITY_VIOLATION', 'unsupported role authority')
        if self.active_documents not in ('accepted_refs', 'not_applicable'):
            raise RouterError('INVALID_CONTRACT', 'explicit active document selection required')
        if not isinstance(self.selected_refs, list):
            raise RouterError('INVALID_CONTRACT', 'selected_refs must be a list')
        if bool(self.selected_refs) != (self.active_documents == 'accepted_refs'):
            raise RouterError('INVALID_CONTRACT', 'active documents not bound')
        for ref in self.selected_refs:
            if (not isinstance(ref, dict) or set(ref) != {'path', 'sha256', 'accepted'}
                    or ref['accepted'] is not True or not isinstance(ref['path'], str)
                    or not isinstance(ref['sha256'], str) or len(ref['sha256']) != 64):
                raise RouterError('INVALID_CONTRACT', 'accepted ref needs exact path and hash')
        for name in ('instruction_precedence', 'required_capabilities'):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, list)
                                      or any(not isinstance(x, str) for x in value)):
                raise RouterError('INVALID_CONTRACT', f'invalid {name}')

    def to_dict(self) -> dict:
        return {field.name: asdict(self)[field.name] for field in fields(self)
                if getattr(self, field.name) is not None}
