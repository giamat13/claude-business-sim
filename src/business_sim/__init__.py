"""A simulated small business that an AI operator runs through a tool interface."""

from .config import default_world
from .operators import DEFAULT_MODEL, ClaudeOperator, RuleBasedOperator
from .simulation import Simulation

__version__ = "0.1.0"

__all__ = [
    "ClaudeOperator",
    "DEFAULT_MODEL",
    "RuleBasedOperator",
    "Simulation",
    "__version__",
    "default_world",
]
