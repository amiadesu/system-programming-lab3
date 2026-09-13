from errors import CompilerError

# Python-level exceptions that can surface while running a valid-looking
# program, mapped to wording that talks about the C program rather than about
# the interpreter's implementation.
_FALLBACK_MESSAGES = {
    ZeroDivisionError: "Ділення на нуль",
    RecursionError: "Занадто глибока рекурсія",
    OverflowError: "Переповнення під час обчислення",
    ValueError: "Некоректна операція над числом",
}


def describe(exception: BaseException) -> str:
    if isinstance(exception, CompilerError):
        return str(exception)
    for exception_type, message in _FALLBACK_MESSAGES.items():
        if isinstance(exception, exception_type):
            return message
    return f"{type(exception).__name__}: {exception}"