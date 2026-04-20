"""AI decision-making, split by domain. AIMixin combines them all."""
from .core import AICoreMixin
from .production import AIProductionMixin
from .civilian import AICivilianMixin
from .worker import AIWorkerMixin
from .settler import AISettlerMixin
from .military import AIMilitaryMixin


class AIMixin(
    AICoreMixin,
    AIProductionMixin,
    AIWorkerMixin,
    AISettlerMixin,
    AIMilitaryMixin,
    AICivilianMixin,
):
    """Aggregates all per-domain AI mixins."""
    pass


__all__ = [
    "AICoreMixin",
    "AIProductionMixin",
    "AIWorkerMixin",
    "AISettlerMixin",
    "AIMilitaryMixin",
    "AICivilianMixin",
    "AIMixin",
]
