"""
Constants shared by several compiler stages.
"""
from dataclasses import dataclass
from enum import StrEnum, IntEnum

class CType(StrEnum):
    INT = "int"
    DOUBLE = "double"
    VOID = "void"

    # Not a real C type: the type type inference assigns to a string literal,
    # which the grammar only allows as the argument of `print`.
    TEXT = "text"


@dataclass(frozen=True)
class ArrayType:
    """
    An array of `element`, with `length` elements.

    `length` is None for a parameter declared `int a[]`, where the size is not
    part of the type - such an array can be indexed but not measured.
    """

    element: CType
    length: int | None = None

    def __str__(self) -> str:
        return f"{self.element}[{self.length if self.length is not None else ''}]"


# A declared type is either a plain C type or an array of one.
ValueType = CType | ArrayType

# Sizes `sizeof` reports, in bytes, matching a typical 64-bit C compiler so
# that `sizeof(a) / sizeof(a[0])` gives the number of elements as it does in C.
TYPE_SIZES = {
    CType.INT: 4,
    CType.DOUBLE: 8,
}
    
class Precedence(IntEnum):
    """
    Operator precedence, from lowest to highest.

    The values are arbitrary, but must be in the same order as C's operator
    precedence table.
    """
        
    WALRUS = 0
    TERNARY = 1
    OR = 2
    AND = 3
    NOT = 4
    COMPARISON = 5
    BITWISE_OR = 6
    BITWISE_XOR = 7
    BITWISE_AND = 8
    SHIFT = 9
    ADDITIVE = 10
    MULTIPLICATIVE = 11
    UNARY = 12
    ATOM = 13
    
    DEFAULT_MINIMUM = TERNARY
    INSIDE_PARENTHESES = WALRUS # absolute minimum precedence

# Specifying the precedence of the operators in the AST is not enough to generate correct Python code, 
# because C and Python disagree about the relative precedence of some operators. 
# The following table records the precedence of each binary operator in Python, 
# as (level of the result, minimum required of the right operand). 
# All of them are left-associative, so the right operand sits one level higher.
BINARY_LEVELS = {
    "|": (Precedence.BITWISE_OR, Precedence.BITWISE_XOR),
    "^": (Precedence.BITWISE_XOR, Precedence.BITWISE_AND),
    "&": (Precedence.BITWISE_AND, Precedence.SHIFT),
    "<<": (Precedence.SHIFT, Precedence.ADDITIVE),
    ">>": (Precedence.SHIFT, Precedence.ADDITIVE),
    "+": (Precedence.ADDITIVE, Precedence.MULTIPLICATIVE),
    "-": (Precedence.ADDITIVE, Precedence.MULTIPLICATIVE),
    "*": (Precedence.MULTIPLICATIVE, Precedence.UNARY),
}

INDENT_UNIT = "    "

#: Pieces of the generated module's preamble, each emitted only when the
#: program actually needs it.
MATH_IMPORT = "import math\n"

#: C leaves an out-of-range subscript undefined, and Python would quietly wrap
#: a negative index round to the end of the list. Neither is reproducible, so
#: the generated code refuses the subscript, exactly as the interpreter does.
ARRAY_HELPERS = (
    "def _bound(sequence, index):\n"
    "    if index < 0 or index >= len(sequence):\n"
    "        raise IndexError(\n"
    "            f\"індекс {index} поза межами масиву довжини {len(sequence)}\"\n"
    "        )\n"
    "    return index\n"
    "\n"
    "\n"
    "def _store(sequence, index, value):\n"
    "    sequence[_bound(sequence, index)] = value\n"
    "    return sequence[index]\n"
)


class Stage(StrEnum):
    """Which compiler stage an error was raised in."""
    LEX = "lex"
    PARSE = "parse"
    SEMANTIC = "semantic"
    RUN = "run"
    COMPILE = "compile"  # fallback: an error not tied to one specific stage


# Keywords, string escapes
RESERVED_WORDS = {
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
    "sizeof": "SIZEOF",
}
ESCAPE_SEQUENCES = {
    "n": "\n", "t": "\t", "r": "\r", "0": "\0",
    "\\": "\\", '"': '"',
}


# Operators
COMPARISON_OPERATORS = {"==", "!=", "<", ">", "<=", ">="}
# Operators C only defines for integer operands.
INTEGER_ONLY_OPERATORS = {"%", "&", "|", "^", "<<", ">>"}
COMPOUND_ASSIGN_OPERATORS = {
    "+=": "+", "-=": "-", "*=": "*", "/=": "/", "%=": "%",
    "&=": "&", "|=": "|", "^=": "^", "<<=": "<<", ">>=": ">>",
}

# Names the generated module uses for itself and that a C identifier
# therefore may not be renamed to shadow.
RESERVED_NAMES = {"math"}

# Guards against a program that never terminates blocking the server.
MAX_STEPS = 1_000_000
MAX_CALL_DEPTH = 500

# Digits after the point that `print` shows for a double, matching C's "%f".
DOUBLE_OUTPUT_PRECISION = 6

INT32_MIN = -(2 ** 31)
INT32_MAX = 2 ** 31 - 1

ENTRY_POINT = "main"