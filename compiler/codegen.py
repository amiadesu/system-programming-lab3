"""
Translation of the AST into Python source text.
"""
from functools import singledispatch

from ast_nodes import (
    Group, Program, VarDecl, FuncDecl, FuncProto, Block, If, While, For,
    DoWhile, Break, Continue, Return, Print, ExprStmt, Assign, CompoundAssign,
    IncDec, BinOp, LogicalOp, UnaryOp, Ternary, Call, Id, Const, StringConst,
)
from constants import (
    COMPARISON_OPERATORS, CType, Precedence, BINARY_LEVELS, INDENT_UNIT, PREAMBLE, DOUBLE_OUTPUT_PRECISION
)
from name_resolution import NameResolution, resolve_names
from type_inference import TypeInformation, infer_types


def generate_python(
    program: Program,
    resolution: NameResolution | None = None,
    types: TypeInformation | None = None,
) -> str:
    resolution = resolution if resolution is not None else resolve_names(program)
    types = types if types is not None else infer_types(program, resolution)
    context = _Context(resolution, types, program)
    body = _generate_statement(program, 0, context)
    preamble = PREAMBLE if context.uses_math else ""
    return preamble + body


class _Context:
    """Per-translation state: replaces the module-level globals of the old
    implementation so two translations can never interfere."""

    def __init__(self, resolution: NameResolution, types: TypeInformation, program: Program):
        self.resolution = resolution
        self.types = types
        self.functions = {
            declaration.name: declaration
            for declaration in program.declarations
            if isinstance(declaration, FuncDecl)
        }
        self.current_return_type = CType.INT
        self.uses_math = False
        self.current_function: str | None = None
        self.continue_prelude: list = []

    def name_of(self, node) -> str:
        return self.resolution.name_of(node)

    def name_of_function(self, c_name: str) -> str:
        return self.resolution.name_of_function(c_name)

    def type_of(self, node) -> str:
        return self.types.type_of(node)


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
    previous_return_type = context.current_return_type
    context.current_function = node.name
    context.current_return_type = node.return_type
    body = _generate_statement(node.body, indent + 1, context)
    context.current_function = previous_function
    context.current_return_type = previous_return_type

    assigned_globals = context.resolution.assigned_globals.get(node.name, [])
    global_stmt = (
        f"{_pad(indent + 1)}global {', '.join(assigned_globals)}\n"
        if assigned_globals
        else ""
    )
    return header + global_stmt + body


@_generate_statement.register(FuncProto)
def _generate_func_proto(node: FuncProto, indent: int, context: _Context) -> str:
    # A prototype only tells the compiler what to expect; Python needs nothing.
    return ""


@_generate_statement.register(VarDecl)
def _generate_var_decl(node: VarDecl, indent: int, context: _Context) -> str:
    name = context.name_of(node)
    if node.value is not None:
        return f"{_pad(indent)}{name} = {_converted(node.value, node.type, context)}\n"
    return f"{_pad(indent)}{name} = {'0.0' if node.type == CType.DOUBLE else '0'}\n"


@_generate_statement.register(If)
def _generate_if(node: If, indent: int, context: _Context) -> str:
    text = f"{_pad(indent)}if {_expression(node.condition, Precedence.DEFAULT_MINIMUM, context)}:\n"
    text += _generate_statement(node.then_branch, indent + 1, context)
    if node.else_branch is not None and node.else_branch.statements:
        text += f"{_pad(indent)}else:\n"
        text += _generate_statement(node.else_branch, indent + 1, context)
    return text


@_generate_statement.register(While)
def _generate_while(node: While, indent: int, context: _Context) -> str:
    text = f"{_pad(indent)}while {_expression(node.condition, Precedence.DEFAULT_MINIMUM, context)}:\n"
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
        _expression(node.condition, Precedence.DEFAULT_MINIMUM, context)
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
    condition = _expression(node.condition, Precedence.COMPARISON, context)

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
    return f"{_pad(indent)}return {_converted(node.value, context.current_return_type, context)}\n"


@_generate_statement.register(Print)
def _generate_print(node: Print, indent: int, context: _Context) -> str:
    if isinstance(node.value, StringConst):
        return f"{_pad(indent)}print({node.value.value!r})\n"
    if context.type_of(node.value) == CType.DOUBLE:
        rendered = _expression(node.value, Precedence.INSIDE_PARENTHESES, context)
        return f'{_pad(indent)}print(f"{{{rendered}:.{DOUBLE_OUTPUT_PRECISION}f}}")\n'
    return f"{_pad(indent)}print({_int_normalised(node.value, context)})\n"


@_generate_statement.register(ExprStmt)
def _generate_expr_stmt(node: ExprStmt, indent: int, context: _Context) -> str:
    inner = node.expression

    if isinstance(inner, Assign):
        target = context.name_of(inner)
        return f"{_pad(indent)}{target} = {_converted(inner.value, CType(context.type_of(inner)), context)}\n"

    if isinstance(inner, CompoundAssign):
        target = context.name_of(inner)
        target_type = CType(context.type_of(inner))
        combined = _compound_value(inner, target, target_type, context)
        if combined is not None:
            return f"{_pad(indent)}{target} = {combined}\n"
        value = _expression(inner.value, Precedence.DEFAULT_MINIMUM, context)
        return f"{_pad(indent)}{target} {inner.operator}= {value}\n"

    if isinstance(inner, IncDec):
        target = context.name_of(inner)
        return f"{_pad(indent)}{target} {inner.operator}= 1\n"

    return f"{_pad(indent)}{_expression(inner, Precedence.DEFAULT_MINIMUM, context)}\n"


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


def _converted(node, target_type: CType, context: _Context) -> str:
    """
    Renders `node` for a slot of `target_type`, applying the C conversion.

    Only narrowing needs code: a double put into an int truncates toward zero.
    Widening the other way is free, because Python's `/` is already true
    division and every other operator gives the same answer for an int as for
    the double it stands for.
    """
    if target_type == CType.INT and context.type_of(node) == CType.DOUBLE:
        context.uses_math = True
        return f"math.trunc({_expression(node, Precedence.INSIDE_PARENTHESES, context)})"
    if target_type == CType.INT:
        return _int_normalised(node, context)
    if context.type_of(node) == CType.INT:
        if isinstance(node, Const):
            return repr(float(node.value))
        return f"float({_expression(node, Precedence.INSIDE_PARENTHESES, context)})"
    return _expression(node, Precedence.INSIDE_PARENTHESES, context)


def _int_normalised(node, context: _Context) -> str:
    """
    Renders `node` so that the result is an `int` and never a `bool`.
    """
    text = _expression(node, Precedence.INSIDE_PARENTHESES, context)
    return f"int({text})" if _yields_bool(node) else text


def _bool_normalised(node, context: _Context) -> str:
    """
    Renders `node` as an operand of `and`/`or`, which return an operand rather than a truth value in Python.
    """
    if _yields_bool(node):
        return _expression(node, Precedence.AND, context)
    return f"bool({_expression(node, Precedence.INSIDE_PARENTHESES, context)})"


def _divide_or_modulo(node: BinOp, left: str, context: _Context) -> str:
    """
    Renders `/` and `%`, neither of which maps onto a Python operator.
    """
    if node.operator == "/" and context.type_of(node) == CType.DOUBLE:
        right = _expression(node.right, Precedence.UNARY, context)
        return f"{left} / {right}"

    context.uses_math = True
    if node.operator == "/":
        right = _expression(node.right, Precedence.UNARY, context)
        return f"math.trunc({left} / {right})"
    right = _expression(node.right, Precedence.DEFAULT_MINIMUM, context)
    return f"int(math.fmod({left}, {right}))"


def _compound_value(node: CompoundAssign, target: str, target_type: CType, context: _Context) -> str | None:
    value_type = context.type_of(node.value)
    narrows = target_type == CType.INT and value_type == CType.DOUBLE

    if node.operator in ("/", "%"):
        right_minimum = Precedence.UNARY if node.operator == "/" else Precedence.DEFAULT_MINIMUM
        right = _expression(node.value, right_minimum, context)
        if node.operator == "/":
            if target_type == CType.DOUBLE or value_type == CType.DOUBLE:
                combined = f"{target} / {right}"
                return f"math.trunc({combined})" if narrows else combined
            context.uses_math = True
            return f"math.trunc({target} / {right})"
        context.uses_math = True
        return f"int(math.fmod({target}, {right}))"

    if narrows:
        context.uses_math = True
        _, right_level = BINARY_LEVELS[node.operator]
        right = _expression(node.value, right_level, context)
        return f"math.trunc({target} {node.operator} {right})"

    return None


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
    return f"({_expression(node.expression, Precedence.INSIDE_PARENTHESES, context)})", Precedence.ATOM


@_generate_expression.register(Assign)
def _generate_assign_expr(node: Assign, context: _Context) -> tuple[str, int]:
    target = context.name_of(node)
    value = _converted(node.value, CType(context.type_of(node)), context)
    return f"{target} := {value}", Precedence.WALRUS


@_generate_expression.register(BinOp)
def _generate_binop_expr(node: BinOp, context: _Context) -> tuple[str, int]:
    if node.operator in ("/", "%"):
        left_minimum = Precedence.MULTIPLICATIVE if node.operator == "/" else Precedence.DEFAULT_MINIMUM
        left = _expression(node.left, left_minimum, context)
        rendered = _divide_or_modulo(node, left, context)
        level = Precedence.MULTIPLICATIVE if rendered.startswith(f"{left} /") else Precedence.ATOM
        return rendered, level

    if node.operator in COMPARISON_OPERATORS:
        # Requiring one level above Precedence.COMPARISON on both sides parenthesises
        # any nested comparison, which is what stops Python from chaining them.
        left = _expression(node.left, Precedence.BITWISE_OR, context)
        right = _expression(node.right, Precedence.BITWISE_OR, context)
        return f"{left} {node.operator} {right}", Precedence.COMPARISON

    level, right_level = BINARY_LEVELS[node.operator]
    left = _expression(node.left, level, context)
    right = _expression(node.right, right_level, context)
    return f"{left} {node.operator} {right}", level


@_generate_expression.register(LogicalOp)
def _generate_logical_expr(node: LogicalOp, context: _Context) -> tuple[str, int]:
    keyword = "and" if node.operator == "&&" else "or"
    level = Precedence.AND if node.operator == "&&" else Precedence.OR
    left = _bool_normalised(node.left, context)
    right = _bool_normalised(node.right, context)
    return f"{left} {keyword} {right}", level


@_generate_expression.register(Ternary)
def _generate_ternary_expr(node: Ternary, context: _Context) -> tuple[str, int]:
    condition = _expression(node.condition, Precedence.OR, context)
    if _yields_bool(node):
        if_true = _expression(node.if_true, Precedence.OR, context)
        if_false = _expression(node.if_false, Precedence.TERNARY, context)
    else:
        if_true = _int_normalised(node.if_true, context)
        if_false = _int_normalised(node.if_false, context)
    return f"{if_true} if {condition} else {if_false}", Precedence.TERNARY


@_generate_expression.register(CompoundAssign)
def _generate_compound_assign_expr(node: CompoundAssign, context: _Context) -> tuple[str, int]:
    target = context.name_of(node)
    target_type = CType(context.type_of(node))
    value = _compound_value(node, target, target_type, context)
    if value is None:
        _, right_level = BINARY_LEVELS[node.operator]
        value = f"{target} {node.operator} {_expression(node.value, right_level, context)}"
    return f"{target} := {value}", Precedence.WALRUS


@_generate_expression.register(IncDec)
def _generate_inc_dec_expr(node: IncDec, context: _Context) -> tuple[str, int]:
    target = context.name_of(node)
    updated = f"{target} := {target} {node.operator} 1"
    if node.is_prefix:
        return updated, Precedence.WALRUS
    undo = "-" if node.operator == "+" else "+"
    return f"({updated}) {undo} 1", Precedence.ADDITIVE


@_generate_expression.register(UnaryOp)
def _generate_unary_expr(node: UnaryOp, context: _Context) -> tuple[str, int]:
    if node.operator == "!":
        return f"not {_expression(node.operand, Precedence.ATOM, context)}", Precedence.NOT
    if node.operator == "~" and _yields_bool(node.operand):
        return f"~{_int_normalised(node.operand, context)}", Precedence.UNARY
    return f"{node.operator}{_expression(node.operand, Precedence.ATOM, context)}", Precedence.UNARY


@_generate_expression.register(Call)
def _generate_call_expr(node: Call, context: _Context) -> tuple[str, int]:
    function = context.functions.get(node.name)
    parameter_types = [param.type for param in function.params] if function else []
    args = ", ".join(
        _converted(argument, parameter_types[index] if index < len(parameter_types) else CType.INT, context)
        for index, argument in enumerate(node.arguments)
    )
    return f"{context.name_of_function(node.name)}({args})", Precedence.ATOM


@_generate_expression.register(Id)
def _generate_id_expr(node: Id, context: _Context) -> tuple[str, int]:
    return context.name_of(node), Precedence.ATOM


@_generate_expression.register(Const)
def _generate_const_expr(node: Const, context: _Context) -> tuple[str, int]:
    return repr(node.value), Precedence.ATOM