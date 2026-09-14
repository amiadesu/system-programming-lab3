"""
Translation of the AST into Python source text.
"""
from functools import singledispatch

from ast_nodes import (
    Group, Program, VarDecl, FuncDecl, Block, If, While, For, DoWhile, Break,
    Continue, Return, Print, ExprStmt, Assign, CompoundAssign, IncDec, BinOp,
    LogicalOp, UnaryOp, Ternary, Call, Id, Const,
)
from name_resolution import NameResolution, resolve_names

INDENT_UNIT = "    "

# Python precedence levels, lowest binds loosest.
#
# For left-associative operations right precedence is one higher than left precedence, 
# so that the right operand of a left-associative operator is parenthesised when it has the same operator.
#
# For right-associative operations it is the other way around.
#
# For comparison operators, both sides are parenthesised when they have the same operator, 
# to prevent Python from chaining them.
PREC_WALRUS = 0
PREC_TERNARY = 1
PREC_OR = 2
PREC_AND = 3
PREC_NOT = 4
PREC_COMPARISON = 5
PREC_BITWISE_OR = 6
PREC_BITWISE_XOR = 7
PREC_BITWISE_AND = 8
PREC_SHIFT = 9
PREC_ADDITIVE = 10
PREC_MULTIPLICATIVE = 11
PREC_UNARY = 12
PREC_ATOM = 13

COMPARISON_OPERATORS = {"==", "!=", "<", ">", "<=", ">="}

# Specifying the precedence of the operators in the AST is not enough to generate correct Python code, 
# because C and Python disagree about the relative precedence of some operators. 
# The following table records the precedence of each binary operator in Python, 
# as (level of the result, minimum required of the right operand). 
# All of them are left-associative, so the right operand sits one level higher.
BINARY_LEVELS = {
    "|": (PREC_BITWISE_OR, PREC_BITWISE_XOR),
    "^": (PREC_BITWISE_XOR, PREC_BITWISE_AND),
    "&": (PREC_BITWISE_AND, PREC_SHIFT),
    "<<": (PREC_SHIFT, PREC_ADDITIVE),
    ">>": (PREC_SHIFT, PREC_ADDITIVE),
    "+": (PREC_ADDITIVE, PREC_MULTIPLICATIVE),
    "-": (PREC_ADDITIVE, PREC_MULTIPLICATIVE),
    "*": (PREC_MULTIPLICATIVE, PREC_UNARY),
}

PREC_DEFAULT_MINIMUM = PREC_TERNARY
PREC_INSIDE_PARENTHESES = PREC_WALRUS # absolute minimum precedence

PREAMBLE = (
    "import math\n\n"
)


def generate_python(program: Program, resolution: NameResolution | None = None) -> str:
    resolution = resolution if resolution is not None else resolve_names(program)
    context = _Context(resolution)
    body = _generate_statement(program, 0, context)
    preamble = PREAMBLE if context.uses_math else ""
    return preamble + body


class _Context:
    """Per-translation state: replaces the module-level globals of the old
    implementation so two translations can never interfere."""

    def __init__(self, resolution: NameResolution):
        self.resolution = resolution
        self.uses_math = False
        self.current_function: str | None = None
        self.continue_prelude: list = []

    def name_of(self, node) -> str:
        return self.resolution.name_of(node)

    def name_of_function(self, c_name: str) -> str:
        return self.resolution.name_of_function(c_name)


def _pad(indent: int) -> str:
    return INDENT_UNIT * indent


def _generate_statement_block(statements: list, indent: int, context: _Context) -> str:
    pieces: list[str] = []
    for position, statement in enumerate(statements):
        # Cosmetic: separate function declaration with a blank line.
        if position > 0 and (
            isinstance(statement, FuncDecl) or isinstance(statements[position - 1], FuncDecl)
        ):
            pieces.append("\n")
        pieces.append(_generate_statement(statement, indent, context))

    body = "".join(pieces)
    if not body.strip():
        return _pad(indent) + "pass\n"
    return body


@singledispatch
def _generate_statement(node, indent: int, context: _Context) -> str:
    raise TypeError(f"No Python codegen rule for statement node {type(node).__name__}")


@_generate_statement.register(Program)
def _generate_program(node: Program, indent: int, context: _Context) -> str:
    return _generate_statement_block(node.declarations, indent, context)


@_generate_statement.register(Block)
def _generate_block(node: Block, indent: int, context: _Context) -> str:
    return _generate_statement_block(node.statements, indent, context)


@_generate_statement.register(FuncDecl)
def _generate_func_decl(node: FuncDecl, indent: int, context: _Context) -> str:
    param_names = ", ".join(context.name_of(param) for param in node.params)
    header = f"{_pad(indent)}def {context.name_of_function(node.name)}({param_names}):\n"

    previous_function = context.current_function
    context.current_function = node.name
    body = _generate_statement(node.body, indent + 1, context)
    context.current_function = previous_function

    assigned_globals = context.resolution.assigned_globals.get(node.name, [])
    global_stmt = (
        f"{_pad(indent + 1)}global {', '.join(assigned_globals)}\n"
        if assigned_globals
        else ""
    )
    return header + global_stmt + body


@_generate_statement.register(VarDecl)
def _generate_var_decl(node: VarDecl, indent: int, context: _Context) -> str:
    name = context.name_of(node)
    if node.value is not None:
        return f"{_pad(indent)}{name} = {_int_normalised(node.value, context)}\n"
    return f"{_pad(indent)}{name} = 0\n"


@_generate_statement.register(If)
def _generate_if(node: If, indent: int, context: _Context) -> str:
    text = f"{_pad(indent)}if {_expression(node.condition, PREC_DEFAULT_MINIMUM, context)}:\n"
    text += _generate_statement(node.then_branch, indent + 1, context)
    if node.else_branch is not None and node.else_branch.statements:
        text += f"{_pad(indent)}else:\n"
        text += _generate_statement(node.else_branch, indent + 1, context)
    return text


@_generate_statement.register(While)
def _generate_while(node: While, indent: int, context: _Context) -> str:
    text = f"{_pad(indent)}while {_expression(node.condition, PREC_DEFAULT_MINIMUM, context)}:\n"
    context.continue_prelude.append(None)
    text += _generate_statement(node.body, indent + 1, context)
    context.continue_prelude.pop()
    return text


@_generate_statement.register(For)
def _generate_for(node: For, indent: int, context: _Context) -> str:
    text = "".join(
        _generate_statement(statement, indent, context) for statement in node.init
    )
    condition = (
        _expression(node.condition, PREC_DEFAULT_MINIMUM, context)
        if node.condition is not None
        else "True"
    )
    step = (
        (lambda step_indent: _generate_statement(ExprStmt(node.step), step_indent, context))
        if node.step is not None
        else None
    )

    context.continue_prelude.append(step)
    body = _generate_statement(node.body, indent + 1, context)
    context.continue_prelude.pop()

    if step is not None:
        # The step also has to run after a normal pass through the body.
        body = ("" if body.strip() == "pass" else body) + step(indent + 1)
    if not body.strip():
        body = f"{_pad(indent + 1)}pass\n"

    return f"{text}{_pad(indent)}while {condition}:\n{body}"


@_generate_statement.register(DoWhile)
def _generate_do_while(node: DoWhile, indent: int, context: _Context) -> str:
    # Python has no do-while, so the loop is expressed as a while True with a break at the end.
    condition = _expression(node.condition, PREC_COMPARISON, context)

    def tail(tail_indent: int) -> str:
        return f"{_pad(tail_indent)}if not {condition}:\n{_pad(tail_indent + 1)}break\n"

    context.continue_prelude.append(tail)
    body = _generate_statement(node.body, indent + 1, context)
    context.continue_prelude.pop()

    body = ("" if body.strip() == "pass" else body) + tail(indent + 1)
    return f"{_pad(indent)}while True:\n{body}"


@_generate_statement.register(Break)
def _generate_break(node: Break, indent: int, context: _Context) -> str:
    return f"{_pad(indent)}break\n"


@_generate_statement.register(Continue)
def _generate_continue(node: Continue, indent: int, context: _Context) -> str:
    prelude = context.continue_prelude[-1] if context.continue_prelude else None
    text = prelude(indent) if prelude is not None else ""
    return f"{text}{_pad(indent)}continue\n"


@_generate_statement.register(Return)
def _generate_return(node: Return, indent: int, context: _Context) -> str:
    if node.value is None:
        return f"{_pad(indent)}return\n"
    return f"{_pad(indent)}return {_int_normalised(node.value, context)}\n"


@_generate_statement.register(Print)
def _generate_print(node: Print, indent: int, context: _Context) -> str:
    return f"{_pad(indent)}print({_int_normalised(node.value, context)})\n"


@_generate_statement.register(ExprStmt)
def _generate_expr_stmt(node: ExprStmt, indent: int, context: _Context) -> str:
    inner = node.expression
    
    if isinstance(inner, Assign):
        target = context.name_of(inner)
        return f"{_pad(indent)}{target} = {_int_normalised(inner.value, context)}\n"

    if isinstance(inner, CompoundAssign):
        target = context.name_of(inner)
        if inner.operator in ("/", "%"):
            return f"{_pad(indent)}{target} = {_divide_or_modulo(inner.operator, target, inner.value, context)}\n"
        value = _expression(inner.value, PREC_DEFAULT_MINIMUM, context)
        return f"{_pad(indent)}{target} {inner.operator}= {value}\n"

    if isinstance(inner, IncDec):
        target = context.name_of(inner)
        return f"{_pad(indent)}{target} {inner.operator}= 1\n"

    return f"{_pad(indent)}{_expression(inner, PREC_DEFAULT_MINIMUM, context)}\n"


def _yields_bool(node) -> bool:
    """
    Returns True when the generated Python for `node` is a `bool` rather than an `int`.
    """
    if isinstance(node, Group):
        return _yields_bool(node.expression)
    if isinstance(node, BinOp):
        if node.operator in COMPARISON_OPERATORS:
            return True
        # `True & False` is a bool in Python, `True & 3` is an int.
        if node.operator in ("&", "|", "^"):
            return _yields_bool(node.left) and _yields_bool(node.right)
        return False
    if isinstance(node, LogicalOp):
        return True
    if isinstance(node, UnaryOp):
        return node.operator == "!"
    if isinstance(node, Ternary):
        return _yields_bool(node.if_true) and _yields_bool(node.if_false)
    return False


def _int_normalised(node, context: _Context) -> str:
    """
    Renders `node` so that the result is an `int` and never a `bool`.
    """
    text = _expression(node, PREC_INSIDE_PARENTHESES, context)
    return f"int({text})" if _yields_bool(node) else text


def _bool_normalised(node, context: _Context) -> str:
    """
    Renders `node` as an operand of `and`/`or`, which return an operand rather than a truth value in Python.
    """
    if _yields_bool(node):
        return _expression(node, PREC_AND, context)
    return f"bool({_expression(node, PREC_INSIDE_PARENTHESES, context)})"


def _divide_or_modulo(operator: str, left: str, right_node, context: _Context) -> str:
    """Shared rendering for `/` and `%`, which cannot use Python's operators."""
    context.uses_math = True
    if operator == "/":
        right = _expression(right_node, PREC_UNARY, context)
        return f"math.trunc({left} / {right})"
    right = _expression(right_node, PREC_DEFAULT_MINIMUM, context)
    return f"int(math.fmod({left}, {right}))"


def _expression(node, minimum_precedence: int, context: _Context) -> str:
    """
    Renders `node`, adding parentheses if its precedence is too low here.
    """
    text, precedence = _generate_expression(node, context)
    if precedence < minimum_precedence:
        return f"({text})"
    return text


@singledispatch
def _generate_expression(node, context: _Context) -> tuple[str, int]:
    raise TypeError(f"No Python codegen rule for expression node {type(node).__name__}")


@_generate_expression.register(Group)
def _generate_group_expr(node: Group, context: _Context) -> tuple[str, int]:
    return f"({_expression(node.expression, PREC_INSIDE_PARENTHESES, context)})", PREC_ATOM


@_generate_expression.register(Assign)
def _generate_assign_expr(node: Assign, context: _Context) -> tuple[str, int]:
    target = context.name_of(node)
    value = _int_normalised(node.value, context)
    return f"{target} := {value}", PREC_WALRUS


@_generate_expression.register(BinOp)
def _generate_binop_expr(node: BinOp, context: _Context) -> tuple[str, int]:
    if node.operator in ("/", "%"):
        left_minimum = PREC_MULTIPLICATIVE if node.operator == "/" else PREC_DEFAULT_MINIMUM
        left = _expression(node.left, left_minimum, context)
        return _divide_or_modulo(node.operator, left, node.right, context), PREC_ATOM

    if node.operator in COMPARISON_OPERATORS:
        # Requiring one level above PREC_COMPARISON on both sides parenthesises
        # any nested comparison, which is what stops Python from chaining them.
        left = _expression(node.left, PREC_BITWISE_OR, context)
        right = _expression(node.right, PREC_BITWISE_OR, context)
        return f"{left} {node.operator} {right}", PREC_COMPARISON

    level, right_level = BINARY_LEVELS[node.operator]
    left = _expression(node.left, level, context)
    right = _expression(node.right, right_level, context)
    return f"{left} {node.operator} {right}", level


@_generate_expression.register(LogicalOp)
def _generate_logical_expr(node: LogicalOp, context: _Context) -> tuple[str, int]:
    keyword = "and" if node.operator == "&&" else "or"
    level = PREC_AND if node.operator == "&&" else PREC_OR
    left = _bool_normalised(node.left, context)
    right = _bool_normalised(node.right, context)
    return f"{left} {keyword} {right}", level


@_generate_expression.register(Ternary)
def _generate_ternary_expr(node: Ternary, context: _Context) -> tuple[str, int]:
    condition = _expression(node.condition, PREC_OR, context)
    if _yields_bool(node):
        if_true = _expression(node.if_true, PREC_OR, context)
        if_false = _expression(node.if_false, PREC_TERNARY, context)
    else:
        if_true = _int_normalised(node.if_true, context)
        if_false = _int_normalised(node.if_false, context)
    return f"{if_true} if {condition} else {if_false}", PREC_TERNARY


@_generate_expression.register(CompoundAssign)
def _generate_compound_assign_expr(node: CompoundAssign, context: _Context) -> tuple[str, int]:
    target = context.name_of(node)
    if node.operator in ("/", "%"):
        value = _divide_or_modulo(node.operator, target, node.value, context)
    else:
        _, right_level = BINARY_LEVELS[node.operator]
        value = f"{target} {node.operator} {_expression(node.value, right_level, context)}"
    return f"{target} := {value}", PREC_WALRUS


@_generate_expression.register(IncDec)
def _generate_inc_dec_expr(node: IncDec, context: _Context) -> tuple[str, int]:
    target = context.name_of(node)
    updated = f"{target} := {target} {node.operator} 1"
    if node.is_prefix:
        return updated, PREC_WALRUS
    undo = "-" if node.operator == "+" else "+"
    return f"({updated}) {undo} 1", PREC_ADDITIVE


@_generate_expression.register(UnaryOp)
def _generate_unary_expr(node: UnaryOp, context: _Context) -> tuple[str, int]:
    if node.operator == "!":
        return f"not {_expression(node.operand, PREC_ATOM, context)}", PREC_NOT
    if node.operator == "~" and _yields_bool(node.operand):
        return f"~{_int_normalised(node.operand, context)}", PREC_UNARY
    return f"{node.operator}{_expression(node.operand, PREC_ATOM, context)}", PREC_UNARY


@_generate_expression.register(Call)
def _generate_call_expr(node: Call, context: _Context) -> tuple[str, int]:
    args = ", ".join(_int_normalised(arg, context) for arg in node.arguments)
    return f"{context.name_of_function(node.name)}({args})", PREC_ATOM


@_generate_expression.register(Id)
def _generate_id_expr(node: Id, context: _Context) -> tuple[str, int]:
    return context.name_of(node), PREC_ATOM


@_generate_expression.register(Const)
def _generate_const_expr(node: Const, context: _Context) -> tuple[str, int]:
    return str(node.value), PREC_ATOM