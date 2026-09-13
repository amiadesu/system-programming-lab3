class CompilerError(Exception):
    """Base class for every error caused by the source program."""
    stage = "compile"


class LexicalError(CompilerError):
    stage = "lex"


class SyntaxErrorAtLine(CompilerError):
    stage = "parse"


class SemanticError(CompilerError):
    stage = "semantic"


class RuntimeErrorInProgram(CompilerError):
    stage = "run"


class ExecutionLimitExceeded(RuntimeErrorInProgram):
    """The program ran too long / too deep to be executed in a web request."""