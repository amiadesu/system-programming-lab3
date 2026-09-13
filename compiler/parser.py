import ply.yacc as yacc

from lexer import tokens, build_lexer
from ast_nodes import (
    Group, Program, VarDecl, Param, FuncDecl, Block, If, While, Return, Print,
    ExprStmt, Assign, BinOp, UnaryOp, Call, Id, Const,
)

precedence = (
    ("nonassoc", "LOWER_THAN_ELSE"),
    ("nonassoc", "ELSE"),
    ("right", "="),
    ("left", "EQ", "NEQ"),
    ("left", "<", ">", "LEQ", "GEQ"),
    ("left", "+", "-"),
    ("left", "*", "/", "%"),
    ("right", "UMINUS"),
)


def p_program(p):
    "program : declaration_list"
    p[0] = Program(p[1])


def p_declaration_list_single(p):
    "declaration_list : declaration"
    p[0] = [p[1]]


def p_declaration_list_multi(p):
    "declaration_list : declaration_list declaration"
    p[0] = p[1] + [p[2]]


def p_declaration(p):
    """declaration : var_declaration
                    | fun_declaration"""
    p[0] = p[1]


def p_var_declaration(p):
    """var_declaration : INT IDENTIFIER ';'
                        | VOID IDENTIFIER ';'"""
    p[0] = VarDecl(p[2])
    
def p_var_declaration_init(p):
    """var_declaration : INT IDENTIFIER '=' expression ';'
                       | VOID IDENTIFIER '=' expression ';'"""
    p[0] = VarDecl(p[2], p[4])

def p_fun_declaration(p):
    """fun_declaration : INT IDENTIFIER '(' params ')' compound_stmt
                        | VOID IDENTIFIER '(' params ')' compound_stmt"""
    p[0] = FuncDecl(p[2], p[4], p[6])


def p_params_empty(p):
    "params : "
    p[0] = []


def p_params_list(p):
    "params : param_list"
    p[0] = p[1]


def p_params_void(p):
    "params : VOID"
    p[0] = []


def p_param_list_single(p):
    "param_list : param"
    p[0] = [p[1]]


def p_param_list_multi(p):
    "param_list : param_list ',' param"
    p[0] = p[1] + [p[3]]


def p_param(p):
    """param : INT IDENTIFIER
              | VOID IDENTIFIER"""
    p[0] = Param(p[2])


def p_compound_stmt(p):
    "compound_stmt : '{' local_declarations statement_list '}'"
    p[0] = Block(p[2] + p[3])


def p_local_declarations_empty(p):
    "local_declarations : "
    p[0] = []


def p_local_declarations_multi(p):
    "local_declarations : local_declarations var_declaration"
    p[0] = p[1] + [p[2]]


def p_statement_list_empty(p):
    "statement_list : "
    p[0] = []


def p_statement_list_multi(p):
    "statement_list : statement_list statement"
    p[0] = p[1] + ([p[2]] if p[2] is not None else [])


def p_statement(p):
    """statement : expression_stmt
                  | compound_stmt
                  | selection_stmt
                  | iteration_stmt
                  | return_stmt
                  | print_stmt"""
    p[0] = p[1]


def p_expression_stmt(p):
    "expression_stmt : expression ';'"
    p[0] = ExprStmt(p[1])


def p_expression_stmt_empty(p):
    "expression_stmt : ';'"
    p[0] = None


def p_print_stmt(p):
    "print_stmt : PRINT '(' expression ')' ';'"
    p[0] = Print(p[3])


def _as_block(statement):
    """Wraps a single statement into a Block for if/while bodies, unless
    it already is one (a literal `{ ... }`) — avoids a redundant nesting
    level in the AST."""
    if statement is None:
        return Block([])
    if isinstance(statement, Block):
        return statement
    return Block([statement])


def p_selection_stmt_if(p):
    "selection_stmt : IF '(' expression ')' statement %prec LOWER_THAN_ELSE"
    p[0] = If(p[3], _as_block(p[5]), None)


def p_selection_stmt_if_else(p):
    "selection_stmt : IF '(' expression ')' statement ELSE statement"
    p[0] = If(p[3], _as_block(p[5]), _as_block(p[7]))


def p_iteration_stmt(p):
    "iteration_stmt : WHILE '(' expression ')' statement"
    p[0] = While(p[3], _as_block(p[5]))


def p_return_stmt_empty(p):
    "return_stmt : RETURN ';'"
    p[0] = Return(None)


def p_return_stmt_value(p):
    "return_stmt : RETURN expression ';'"
    p[0] = Return(p[2])


def p_expression_assign(p):
    "expression : IDENTIFIER '=' expression"
    p[0] = Assign(p[1], p[3])


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
                   | expression '%' expression"""
    p[0] = BinOp(p[2], p[1], p[3])


def p_expression_unary_minus(p):
    "expression : '-' expression %prec UMINUS"
    p[0] = UnaryOp("-", p[2])


def p_expression_group(p):
    "expression : '(' expression ')'"
    p[0] = Group(p[2])


def p_expression_id(p):
    "expression : IDENTIFIER"
    p[0] = Id(p[1])


def p_expression_const(p):
    "expression : INTEGER_CONST"
    p[0] = Const(p[1])


def p_expression_call(p):
    "expression : IDENTIFIER '(' args ')'"
    p[0] = Call(p[1], p[3])


def p_args_empty(p):
    "args : "
    p[0] = []


def p_args_list(p):
    "args : arg_list"
    p[0] = p[1]


def p_arg_list_single(p):
    "arg_list : expression"
    p[0] = [p[1]]


def p_arg_list_multi(p):
    "arg_list : arg_list ',' expression"
    p[0] = p[1] + [p[3]]


def p_error(p):
    if p is None:
        raise SyntaxError("Unexpected end of input")
    raise SyntaxError(f"Syntax error at line {p.lineno}: unexpected {p.value!r}")


_lexer = build_lexer()
_parser = yacc.yacc(write_tables=False, debug=False)


def parse_source(source_code: str) -> Program:
    """Lexes and parses `source_code`, returning the AST root."""
    _lexer.lineno = 1
    return _parser.parse(source_code, lexer=_lexer)
