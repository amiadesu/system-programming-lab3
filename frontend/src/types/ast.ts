export interface AstNode {
  type: string;
  label: string | null;
  role: string | null;
  children: AstNode[];
}

export interface CompileResult {
  ast: AstNode;
  pythonCode: string;
  codegenError: string | null;
  warnings: string[];
  executionOutput: string;
  executionError: string | null;
}

export interface Example {
  name: string;
  sourceCode: string;
}