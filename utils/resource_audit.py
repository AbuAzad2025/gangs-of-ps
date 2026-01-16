from contextvars import ContextVar

_RESOURCE_MUTATION_ALLOWED: ContextVar[bool] = ContextVar(
    "resource_mutation_allowed", default=False)


def allow_resource_mutation() -> object:
    return _RESOURCE_MUTATION_ALLOWED.set(True)


def disallow_resource_mutation(token: object) -> None:
    _RESOURCE_MUTATION_ALLOWED.reset(token)


def is_resource_mutation_allowed() -> bool:
    try:
        return bool(_RESOURCE_MUTATION_ALLOWED.get())
    except Exception:
        return False
