import ply.lex as lex

reserved_words = {
    "int": "INT",
    "void": "VOID",
    "if": "IF",
    "else": "ELSE",
    "while": "WHILE",
    "return": "RETURN",
    "print": "PRINT",
}

tokens = [
    "IDENTIFIER",
    "INTEGER_CONST",
    "EQ", "NEQ", "LEQ", "GEQ",
] + list(reserved_words.values())

literals = ["+", "-", "*", "/", "%", "=", "<", ">", "(", ")", "{", "}", ";", ","]

t_EQ = r"=="
t_NEQ = r"!="
t_LEQ = r"<="
t_GEQ = r">="

t_ignore = " \t\r"


def t_IDENTIFIER(t):
    r"[a-zA-Z_][a-zA-Z0-9_]*"
    t.type = reserved_words.get(t.value, "IDENTIFIER")
    return t


def t_INTEGER_CONST(t):
    r"\d+"
    t.value = int(t.value)
    return t


def t_line_comment(t):
    r"//.*"
    pass  # ignored, no token produced


def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)


def t_error(t):
    raise SyntaxError(f"Unexpected character {t.value[0]!r} at line {t.lexer.lineno}")


def build_lexer():
    return lex.lex()
