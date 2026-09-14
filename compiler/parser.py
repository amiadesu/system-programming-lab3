import functools

import ply.yacc as yacc

from lexer import tokens, build_lexer
from errors import SemanticError, SyntaxErrorAtLine
from constants import COMPOUND_ASSIGN_OPERATORS, CType
from ast_nodes import (
    Group, Program, VarDecl, Param, FuncDecl, FuncProto, Block, If, While, For,
    DoWhile, Break, Continue, Return, Print, ExprStmt, Assign, CompoundAssign,
    IncDec, BinOp, LogicalOp, UnaryOp, Ternary, Call, Id, Const, StringConst,
)

# PLY normally infers the start symbol from the rule defined first, ordering
# rules by the line number of their function. `@_tracked` gives every rule the
# decorator's own line number, so that inference no longer works and the start
# symbol has to be named here.
start = "program"

# Lowest precedence first, mirroring the C operator table.
precedence = (
    ("nonassoc", "LOWER_THAN_ELSE"),
    ("nonassoc", "ELSE"),
    ("right", "=", "PLUSEQ", "MINUSEQ", "TIMESEQ", "DIVEQ", "MODEQ",
     "ANDEQ", "OREQ", "XOREQ", "SHLEQ", "SHREQ"),
    ("right", "?", ":"),
    ("left", "OR"),
    ("left", "AND"),
    ("left", "|"),
    ("left", "^"),
    ("left", "&"),
    ("left", "EQ", "NEQ"),
    ("left", "<", ">", "LEQ", "GEQ"),
    ("left", "SHL", "SHR"),
    ("left", "+", "-"),
    ("left", "*", "/", "%"),
    ("right", "UNARY"),
)


def _line_of(production) -> int | None:
    """
    First source line covered by a production.
    """
    for position in range(1, len(production)):
        line = production.lineno(position)
        if line:
            return line
        span = production.linespan(position)
        if span and span[0]:
            return span[0]
    return None


def _tracked(rule):
    """
    Records the source line on the node a grammar rule produced.
    """

    @functools.wraps(rule)
    def wrapper(production):
        rule(production)
        node = production[0]
        if node is not None and getattr(node, "line", "missing") is None:
            node.line = _line_of(production)

    return wrapper


def _reject_void_object(type_name: CType, object_name: str, line: int) -> None:
    """`void` is a valid type specifier but not a valid type for storage."""
    if type_name == CType.VOID:
        raise SemanticError(
            f"Рядок {line}: змінна '{object_name}' не може мати тип void"
        )


@_tracked
def p_program(p):
    "program : declaration_list"
    p[0] = Program(p[1])


@_tracked
def p_declaration_list_single(p):
    "declaration_list : declaration"
    p[0] = _as_statements(p[1])


@_tracked
def p_declaration_list_multi(p):
    "declaration_list : declaration_list declaration"
    p[0] = p[1] + _as_statements(p[2])


@_tracked
def p_declaration(p):
    """declaration : var_declaration
                    | fun_declaration"""
    p[0] = p[1]


@_tracked
def p_type_specifier(p):
    """type_specifier : INT
                       | DOUBLE
                       | VOID"""
    p[0] = CType(p[1])


def p_declaration_specifier(p):
    """declaration_specifier : type_specifier
                              | CONST type_specifier"""
    # (type, is_const).
    p[0] = (p[len(p) - 1], len(p) == 3)


def p_var_declaration(p):
    "var_declaration : declaration_specifier init_declarator_list ';'"
    # One declaration may introduce several variables, so this rule produces a
    # list of nodes rather than a single one.
    type_name, is_const = p[1]
    declarations = []
    for name, value, line in p[2]:
        _reject_void_object(type_name, name, line)
        if is_const and value is None:
            raise SemanticError(
                f"Рядок {line}: константу '{name}' треба ініціалізувати при оголошенні"
            )
        declarations.append(VarDecl(type_name, name, value, is_const=is_const, line=line))
    p[0] = declarations


def p_init_declarator_list_single(p):
    "init_declarator_list : init_declarator"
    p[0] = [p[1]]


def p_init_declarator_list_multi(p):
    "init_declarator_list : init_declarator_list ',' init_declarator"
    p[0] = p[1] + [p[3]]


def p_init_declarator(p):
    "init_declarator : IDENTIFIER"
    p[0] = (p[1], None, p.lineno(1))


def p_init_declarator_init(p):
    "init_declarator : IDENTIFIER '=' expression"
    p[0] = (p[1], p[3], p.lineno(1))


def _reject_const_return_type(is_const: bool, name: str, line: int | None) -> None:
    if is_const:
        position = f"Рядок {line}: " if line else ""
        raise SemanticError(f"{position}const не застосовується до типу, який повертає '{name}'")


@_tracked
def p_fun_declaration(p):
    "fun_declaration : declaration_specifier IDENTIFIER '(' params ')' compound_stmt"
    type_name, is_const = p[1]
    _reject_const_return_type(is_const, p[2], p.lineno(2))
    p[0] = FuncDecl(type_name, p[2], p[4], p[6])


@_tracked
def p_fun_prototype(p):
    "fun_declaration : declaration_specifier IDENTIFIER '(' params ')' ';'"
    type_name, is_const = p[1]
    _reject_const_return_type(is_const, p[2], p.lineno(2))
    p[0] = FuncProto(type_name, p[2], p[4])


@_tracked
def p_params_empty(p):
    "params : "
    p[0] = []


@_tracked
def p_params_list(p):
    "params : param_list"
    p[0] = p[1]


@_tracked
def p_params_void(p):
    "params : VOID"
    p[0] = []


@_tracked
def p_param_list_single(p):
    "param_list : param"
    p[0] = [p[1]]


@_tracked
def p_param_list_multi(p):
    "param_list : param_list ',' param"
    p[0] = p[1] + [p[3]]


@_tracked
def p_param(p):
    "param : declaration_specifier IDENTIFIER"
    type_name, is_const = p[1]
    _reject_void_object(type_name, p[2], p.lineno(2))
    p[0] = Param(type_name, p[2], is_const=is_const)


@_tracked
def p_compound_stmt(p):
    "compound_stmt : '{' statement_list '}'"
    p[0] = Block(p[2])


@_tracked
def p_statement_list_empty(p):
    "statement_list : "
    p[0] = []


@_tracked
def p_statement_list_multi(p):
    "statement_list : statement_list statement"
    p[0] = p[1] + _as_statements(p[2])


@_tracked
def p_statement(p):
    """statement : expression_stmt
                  | var_declaration
                  | compound_stmt
                  | selection_stmt
                  | iteration_stmt
                  | jump_stmt
                  | return_stmt
                  | print_stmt"""
    p[0] = p[1]


@_tracked
def p_expression_stmt(p):
    "expression_stmt : expression ';'"
    p[0] = ExprStmt(p[1])


@_tracked
def p_expression_stmt_empty(p):
    "expression_stmt : ';'"
    p[0] = None


@_tracked
def p_print_stmt(p):
    "print_stmt : PRINT '(' expression ')' ';'"
    p[0] = Print(p[3])


@_tracked
def p_print_stmt_text(p):
    "print_stmt : PRINT '(' STRING_LITERAL ')' ';'"
    p[0] = Print(StringConst(p[3], line=p.lineno(3) or None))


def _as_statements(statement) -> list:
    """Normalises a `statement` into a list.

    A single declaration may expand into several nodes (`int a = 1, b;`), and
    an empty statement into none at all.
    """
    if statement is None:
        return []
    if isinstance(statement, list):
        return statement
    return [statement]


def _as_block(statement):
    """Wraps a single statement into a Block for if/while bodies, unless
    it already is one (a literal `{ ... }`) — avoids a redundant nesting
    level in the AST."""
    if isinstance(statement, Block):
        return statement
    return Block(_as_statements(statement))


@_tracked
def p_selection_stmt_if(p):
    "selection_stmt : IF '(' expression ')' statement %prec LOWER_THAN_ELSE"
    p[0] = If(p[3], _as_block(p[5]), None)


@_tracked
def p_selection_stmt_if_else(p):
    "selection_stmt : IF '(' expression ')' statement ELSE statement"
    p[0] = If(p[3], _as_block(p[5]), _as_block(p[7]))


@_tracked
def p_iteration_stmt_while(p):
    "iteration_stmt : WHILE '(' expression ')' statement"
    p[0] = While(p[3], _as_block(p[5]))


@_tracked
def p_iteration_stmt_do_while(p):
    "iteration_stmt : DO statement WHILE '(' expression ')' ';'"
    p[0] = DoWhile(_as_block(p[2]), p[5])


@_tracked
def p_iteration_stmt_for(p):
    "iteration_stmt : FOR '(' for_init for_condition ';' for_step ')' statement"
    p[0] = For(p[3], p[4], p[6], _as_block(p[8]))


def p_for_init_declaration(p):
    "for_init : var_declaration"
    # `var_declaration` already consumes its own ';'.
    p[0] = p[1]


def p_for_init_expression(p):
    "for_init : expression ';'"
    p[0] = [ExprStmt(p[1], line=p.lineno(2) or None)]


def p_for_init_empty(p):
    "for_init : ';'"
    p[0] = []


def p_for_condition(p):
    "for_condition : expression"
    p[0] = p[1]


def p_for_condition_empty(p):
    "for_condition : "
    p[0] = None


def p_for_step(p):
    "for_step : expression"
    p[0] = p[1]


def p_for_step_empty(p):
    "for_step : "
    p[0] = None


@_tracked
def p_jump_stmt_break(p):
    "jump_stmt : BREAK ';'"
    p[0] = Break()


@_tracked
def p_jump_stmt_continue(p):
    "jump_stmt : CONTINUE ';'"
    p[0] = Continue()


@_tracked
def p_return_stmt_empty(p):
    "return_stmt : RETURN ';'"
    p[0] = Return(None)


@_tracked
def p_return_stmt_value(p):
    "return_stmt : RETURN expression ';'"
    p[0] = Return(p[2])


@_tracked
def p_expression_assign(p):
    "expression : IDENTIFIER '=' expression"
    p[0] = Assign(p[1], p[3])


@_tracked
def p_expression_compound_assign(p):
    """expression : IDENTIFIER PLUSEQ expression
                   | IDENTIFIER MINUSEQ expression
                   | IDENTIFIER TIMESEQ expression
                   | IDENTIFIER DIVEQ expression
                   | IDENTIFIER MODEQ expression
                   | IDENTIFIER ANDEQ expression
                   | IDENTIFIER OREQ expression
                   | IDENTIFIER XOREQ expression
                   | IDENTIFIER SHLEQ expression
                   | IDENTIFIER SHREQ expression"""
    p[0] = CompoundAssign(COMPOUND_ASSIGN_OPERATORS[p[2]], p[1], p[3])


@_tracked
def p_expression_ternary(p):
    "expression : expression '?' expression ':' expression"
    p[0] = Ternary(p[1], p[3], p[5])


@_tracked
def p_expression_logical(p):
    """expression : expression AND expression
                   | expression OR expression"""
    p[0] = LogicalOp(p[2], p[1], p[3])


@_tracked
def p_expression_prefix_incdec(p):
    """expression : INC IDENTIFIER %prec UNARY
                   | DEC IDENTIFIER %prec UNARY"""
    p[0] = IncDec(p[1][0], p[2], is_prefix=True)


@_tracked
def p_expression_postfix_incdec(p):
    """expression : IDENTIFIER INC
                   | IDENTIFIER DEC"""
    p[0] = IncDec(p[2][0], p[1], is_prefix=False)


@_tracked
def p_expression_binop(p):
    """expression : expression EQ expression
                   | expression NEQ expression
                   | expression '<' expression
                   | expression '>' expression
                   | expression LEQ expression
                   | expression GEQ expression
                   | expression '+' expression
                   | expression '-' expression
                   | expression '*' expression
                   | expression '/' expression
                   | expression '%' expression
                   | expression '&' expression
                   | expression '|' expression
                   | expression '^' expression
                   | expression SHL expression
                   | expression SHR expression"""
    p[0] = BinOp(p[2], p[1], p[3])


@_tracked
def p_expression_unary(p):
    """expression : '-' expression %prec UNARY
                   | '!' expression %prec UNARY
                   | '~' expression %prec UNARY"""
    p[0] = UnaryOp(p[1], p[2])


@_tracked
def p_expression_group(p):
    "expression : '(' expression ')'"
    p[0] = Group(p[2])


@_tracked
def p_expression_id(p):
    "expression : IDENTIFIER"
    p[0] = Id(p[1])


@_tracked
def p_expression_const(p):
    """expression : INTEGER_CONST
                   | DOUBLE_CONST"""
    p[0] = Const(p[1])


@_tracked
def p_expression_call(p):
    "expression : IDENTIFIER '(' args ')'"
    p[0] = Call(p[1], p[3])


@_tracked
def p_args_empty(p):
    "args : "
    p[0] = []


@_tracked
def p_args_list(p):
    "args : arg_list"
    p[0] = p[1]


@_tracked
def p_arg_list_single(p):
    "arg_list : expression"
    p[0] = [p[1]]


@_tracked
def p_arg_list_multi(p):
    "arg_list : arg_list ',' expression"
    p[0] = p[1] + [p[3]]


def p_error(p):
    if p is None:
        raise SyntaxErrorAtLine("Неочікуваний кінець вхідного тексту")
    raise SyntaxErrorAtLine(
        f"Рядок {p.lineno}: синтаксична помилка біля {p.value!r}"
    )


_lexer = build_lexer()
_parser = yacc.yacc(write_tables=False, debug=False)


def parse_source(source_code: str) -> Program:
    """Lexes and parses `source_code`, returning the AST root."""
    _lexer.lineno = 1
    return _parser.parse(source_code, lexer=_lexer, tracking=True)