from collections.abc import Callable
from typing import Any

AnalysisParams = dict[str, Any]
AnalysisResult = dict[str, Any]
AnalysisFunction = Callable[[str, AnalysisParams], AnalysisResult]

# The core stays metric-agnostic: approved functions register at process start.
REGISTRY: dict[str, AnalysisFunction] = {}


class UnknownAnalysisFunction(LookupError):
    """Raised when a deployed analysis function is not registered by name."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Unknown analysis function: {name}")


def register_analysis(name: str) -> Callable[[AnalysisFunction], AnalysisFunction]:
    """Register a deploy-time analysis function under its stable public name."""

    def decorator(fn: AnalysisFunction) -> AnalysisFunction:
        REGISTRY[name] = fn
        return fn

    return decorator


def run(name: str, wav_path: str, params: AnalysisParams) -> AnalysisResult:
    """Resolve and execute a registered function without interpreting its result."""
    try:
        function = REGISTRY[name]
    except KeyError as exc:
        raise UnknownAnalysisFunction(name) from exc
    return function(wav_path, params)


def list_functions() -> list[str]:
    return sorted(REGISTRY.keys())
