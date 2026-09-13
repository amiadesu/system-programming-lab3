import "./PythonOutput.css";

interface PythonOutputProps {
  pythonCode: string;
  codegenError: string | null;
  warnings: string[];
  executionOutput: string;
  executionError: string | null;
}

export default function PythonOutput({
  pythonCode,
  codegenError,
  warnings,
  executionOutput,
  executionError,
}: PythonOutputProps) {
  return (
    <div className="python-output">
      <section className="python-output-section">
        <h2 className="python-output-heading">Згенерований Python</h2>
        {codegenError && <div className="python-output-error">{codegenError}</div>}
        {warnings.map((warning) => (
          <div key={warning} className="python-output-notice">
            {warning}
          </div>
        ))}
        <pre className="python-output-code">
          <code>{pythonCode || "# код з'явиться тут після компіляції"}</code>
        </pre>
      </section>

      <section className="python-output-section">
        <h2 className="python-output-heading">Результат виконання (інтерпретатор AST)</h2>
        <pre
          className={
            executionError ? "python-output-terminal python-output-terminal--error" : "python-output-terminal"
          }
        >
          {executionError ?? (executionOutput || "—")}
        </pre>
      </section>
    </div>
  );
}