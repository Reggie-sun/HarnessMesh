"""Image-only process limits; legacy project Budgets remain unchanged."""
from dataclasses import dataclass
import math

from .contracts import RouterError


@dataclass(frozen=True)
class ImageProcessBudgets:
    wall_seconds: float
    idle_seconds: float
    request_limit: int
    output_bytes: int
    context_bytes: int
    generation_tokens: int | None
    observed_output_tokens_limit: int | None = None

    def __post_init__(self):
        if self.generation_tokens is None:
            if type(self.observed_output_tokens_limit) is not int or self.observed_output_tokens_limit != 2048:
                raise RouterError('INVALID_IMAGE_PROCESS_BUDGET')
        elif self.observed_output_tokens_limit is not None:
            raise RouterError('INVALID_IMAGE_PROCESS_BUDGET')
        limits = {'wall_seconds': 3600, 'idle_seconds': 3600, 'request_limit': 64,
                  'output_bytes': 8 * 1024 * 1024, 'context_bytes': 32 * 1024 * 1024,
                  'generation_tokens': 32000}
        for name, maximum in limits.items():
            value = getattr(self, name)
            if name == 'generation_tokens' and value is None:
                continue
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or not 0 < value <= maximum
                    or (name not in ('wall_seconds', 'idle_seconds') and type(value) is not int)):
                raise RouterError('INVALID_IMAGE_PROCESS_BUDGET')
        if self.idle_seconds > self.wall_seconds:
            raise RouterError('INVALID_IMAGE_PROCESS_BUDGET')

    @classmethod
    def from_task(cls, task):
        value = task['budgets']
        return cls(**{name: value[name] for name in cls.__dataclass_fields__ if name in value})
