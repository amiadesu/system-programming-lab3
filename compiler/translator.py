from dataclasses import dataclass

from parser import parse_source
from semantic_analysis import analyse
from name_resolution import resolve_names
from type_inference import infer_types
from codegen import generate_python
from interpreter import Interpreter
from ast_serializer import ast_to_dict

from error_normalization import describe as _describe_error


@dataclass
class TranslationResult:
    ast: dict | None
    python_code: str
    codegen_error: str | None
    warnings: list[str]
    execution_output: str
    execution_error: str | None


def translate(source_code: str) -> TranslationResult:
    ast = parse_source(source_code)
    analysis = analyse(ast)
    resolution = resolve_names(ast)
    types = infer_types(ast, resolution)
    python_code = generate_python(ast, resolution, types)

    codegen_error = None
    try:
        compile(python_code, "<generated>", "exec")
    except SyntaxError as error:
        codegen_error = f"Згенеровано некоректний Python: {error}"

    execution_output = ""
    execution_error = None
    try:
        interpreter = Interpreter(ast, types)
        interpreter.run()
        execution_output = "\n".join(interpreter.output_lines)
    except Exception as error:
        execution_error = _describe_error(error)

    return TranslationResult(
        ast=ast_to_dict(ast),
        python_code=python_code,
        codegen_error=codegen_error,
        warnings=analysis.warnings,
        execution_output=execution_output,
        execution_error=execution_error,
    )