from constants import Stage


class CompilerError(Exception):
    """Base class for every error caused by the source program."""
    stage = Stage.COMPILE


class LexicalError(CompilerError):
    stage = Stage.LEX


class SyntaxErrorAtLine(CompilerError):
    stage = Stage.PARSE


class SemanticError(CompilerError):
    stage = Stage.SEMANTIC


class RuntimeErrorInProgram(CompilerError):
    stage = Stage.RUN


class ExecutionLimitExceeded(RuntimeErrorInProgram):
    """The program ran too long / too deep to be executed in a web request."""


def error_prefix(node) -> str:
    """Source-position prefix for an error message, when the
    node carries a line number, or "" when it does not."""
    line = getattr(node, "line", None)
    return f"Рядок {line}: " if line else ""