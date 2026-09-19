"""Explicit Gemini backend selection; no model or profile fallback."""
from dataclasses import asdict, dataclass

from ..contracts import RouterError, canonical_bytes, hash_bytes


@dataclass(frozen=True)
class Profile:
    name: str
    client_model: str
    wire_model: str
    context_tokens: int
    backend: str = 'gemini'
    runtime: str = 'gemini-cli'
    policy_version: int = 1

    def to_dict(self) -> dict:
        value = asdict(self)
        return value | {'sha256': hash_bytes(canonical_bytes(value))}


def profile(name: str) -> Profile:
    if name != 'worker':
        raise RouterError('UNKNOWN_PROFILE', 'explicit worker required')
    return Profile('worker', 'gemini-3.5-flash', 'gemini-3.5-flash', 1_000_000)
