import contextvars


_ctx_var: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "revise_ctx", default=None
)


def reset_ctx() -> None:
    _ctx_var.set({})


def get_ctx() -> dict:
    value = _ctx_var.get()
    if value is None:
        reset_ctx()
        return _ctx_var.get() or {}
    return value
