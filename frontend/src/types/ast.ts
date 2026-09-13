export interface AstNode {
  type: string;
  label: string | null;
  children: AstNode[];
}

export interface CompileResult {
  ast: AstNode;
  pythonCode: string;
  executionOutput: string;
  executionError: string | null;
}
