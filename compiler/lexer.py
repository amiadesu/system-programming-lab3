import ply.lex as lex

from errors import LexicalError

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

t_ignore = " \t\r\f\v"


def t_block_comment(t):
    r"/\*(.|\n)*?\*/"
    t.lexer.lineno += t.value.count("\n")
    pass # ignored, no token produced


def t_line_comment(t):
    r"//[^\n]*"
    pass  # ignored, no token produced


def t_unterminated_block_comment(t):
    r"/\*"
    raise LexicalError(f"Незакритий коментар /* починаючи з рядка {t.lexer.lineno}")


def t_IDENTIFIER(t):
    r"[a-zA-Z_][a-zA-Z0-9_]*"
    t.type = reserved_words.get(t.value, "IDENTIFIER")
    return t


def t_INTEGER_CONST(t):
    r"\d+"
    t.value = int(t.value)
    return t


def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)


def t_error(t):
    raise LexicalError(
        f"Рядок {t.lexer.lineno}: неочікуваний символ {t.value[0]!r}"
    )


def build_lexer():
    return lex.lex()