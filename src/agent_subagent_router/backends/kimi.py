from dataclasses import asdict, dataclass

from ..contracts import RouterError, canonical_bytes, hash_bytes


@dataclass(frozen=True)
class Profile:
    name: str
    client_model: str
    wire_model: str
    effort: str
    context_tokens: int
    backend: str = 'kimi'
    runtime: str = 'claude-code'
    endpoint: str = 'https://api.kimi.ai/coding/'
    policy_version: int = 1

    def to_dict(self):
        value = asdict(self)
        return value | {'sha256': hash_bytes(canonical_bytes(value))}


def profile(name: str) -> Profile:
    values = {'worker': Profile('worker', 'k3-256k', 'k3-256k', 'high', 262144),
              'deep': Profile('deep', 'k3[1m]', 'k3', 'max', 1048576)}
    if name not in values:
        raise RouterError('UNKNOWN_PROFILE', 'explicit worker or deep required')
    return values[name]
