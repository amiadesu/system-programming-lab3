import ply.lex as lex

from errors import LexicalError

reserved_words = {
    "int": "INT",
    "double": "DOUBLE",
    "void": "VOID",
    "const": "CONST",
    "if": "IF",
    "else": "ELSE",
    "while": "WHILE",
    "for": "FOR",
    "do": "DO",
    "break": "BREAK",
    "continue": "CONTINUE",
    "return": "RETURN",
    "print": "PRINT",
}

tokens = [
    "IDENTIFIER",
    "INTEGER_CONST",
    "DOUBLE_CONST",
    "STRING_LITERAL",
    "EQ", "NEQ", "LEQ", "GEQ",
    "AND", "OR",
    "SHL", "SHR",
    "INC", "DEC",
    "PLUSEQ", "MINUSEQ", "TIMESEQ", "DIVEQ", "MODEQ",
    "ANDEQ", "OREQ", "XOREQ", "SHLEQ", "SHREQ",
] + list(reserved_words.values())

literals = [
    "+", "-", "*", "/", "%", "=", "<", ">", "!", "~", "&", "|", "^", "?", ":",
    "(", ")", "{", "}", ";", ",",
]

t_SHLEQ = r"<<="
t_SHREQ = r">>="
t_EQ = r"=="
t_NEQ = r"!="
t_LEQ = r"<="
t_GEQ = r">="
t_AND = r"&&"
t_OR = r"\|\|"
t_SHL = r"<<"
t_SHR = r">>"
t_INC = r"\+\+"
t_DEC = r"--"
t_PLUSEQ = r"\+="
t_MINUSEQ = r"-="
t_TIMESEQ = r"\*="
t_DIVEQ = r"/="
t_MODEQ = r"%="
t_ANDEQ = r"&="
t_OREQ = r"\|="
t_XOREQ = r"\^="

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


ESCAPE_SEQUENCES = {
    "n": "\n", "t": "\t", "r": "\r", "0": "\0",
    "\\": "\\", '"': '"',
}


def t_STRING_LITERAL(t):
    r'"(\\.|[^"\\\n])*"'
    # Only usable as the argument of `print`; the grammar allows it nowhere else.
    text = t.value[1:-1]
    result = []
    index = 0
    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text):
            escape = text[index + 1]
            if escape not in ESCAPE_SEQUENCES:
                raise LexicalError(
                    f"Рядок {t.lexer.lineno}: невідома escape-послідовність '\\{escape}'"
                )
            result.append(ESCAPE_SEQUENCES[escape])
            index += 2
        else:
            result.append(text[index])
            index += 1
    t.value = "".join(result)
    return t


def t_unterminated_string(t):
    r'"[^"\n]*'
    raise LexicalError(f"Рядок {t.lexer.lineno}: незакритий рядковий літерал")


def t_IDENTIFIER(t):
    r"[a-zA-Z_][a-zA-Z0-9_]*"
    t.type = reserved_words.get(t.value, "IDENTIFIER")
    return t


def t_DOUBLE_CONST(t):
    r"(\d+\.\d*|\.\d+)([eE][+-]?\d+)?|\d+[eE][+-]?\d+"
    t.value = float(t.value)
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