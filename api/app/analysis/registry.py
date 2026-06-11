from typing import Callable

# El núcleo es AGNÓSTICO: no conoce la semántica de las métricas.
# El técnico registra funciones por nombre; el sistema ejecuta y persiste el dict.
REGISTRY: dict[str, Callable[[str, dict], dict]] = {}


class UnknownAnalysisFunction(Exception):
    pass


def register_analysis(name: str):
    def deco(fn: Callable[[str, dict], dict]):
        REGISTRY[name] = fn
        return fn
    return deco


def run(name: str, wav_path: str, params: dict | None = None) -> dict:
    if name not in REGISTRY:
        raise UnknownAnalysisFunction(name)
    return REGISTRY[name](wav_path, params or {})


def list_functions() -> list[str]:
    return sorted(REGISTRY.keys())
