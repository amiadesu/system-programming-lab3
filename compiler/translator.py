from dataclasses import dataclass

from parser import parse_source
from codegen import generate_python
from interpreter import Interpreter
from ast_serializer import ast_to_dict


@dataclass
class TranslationResult:
    ast: dict | None
    python_code: str
    execution_output: str
    execution_error: str | None


def translate(source_code: str) -> TranslationResult:
    ast = parse_source(source_code)
    python_code = generate_python(ast)

    execution_output = ""
    execution_error = None
    try:
        interpreter = Interpreter(ast)
        interpreter.run()
        execution_output = "\n".join(interpreter.output_lines)
    except Exception as error:
        execution_error = str(error)

    return TranslationResult(
        ast=ast_to_dict(ast),
        python_code=python_code,
        execution_output=execution_output,
        execution_error=execution_error,
    )
