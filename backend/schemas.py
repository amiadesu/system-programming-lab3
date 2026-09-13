from pydantic import BaseModel


class CompileRequest(BaseModel):
    source_code: str


class AstNode(BaseModel):
    type: str
    label: str | None = None
    children: list["AstNode"] = []


class CompileResponse(BaseModel):
    ast: AstNode
    python_code: str
    execution_output: str
    execution_error: str | None = None


class CompileErrorResponse(BaseModel):
    message: str
