from pydantic import BaseModel, Field


class CompileRequest(BaseModel):
    source_code: str


class AstNode(BaseModel):
    type: str
    label: str | None = None
    role: str | None = None
    children: list["AstNode"] = Field(default_factory=list)


class CompileResponse(BaseModel):
    ast: AstNode
    python_code: str
    reconstructed_source: str = ""
    codegen_error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    execution_output: str
    execution_error: str | None = None


class Example(BaseModel):
    name: str
    source_code: str