import "./PythonOutput.css";

interface PythonOutputProps {
  pythonCode: string;
  executionOutput: string;
  executionError: string | null;
}

export default function PythonOutput({
  pythonCode,
  executionOutput,
  executionError,
}: PythonOutputProps) {
  return (
    <div className="python-output">
      <section className="python-output-section">
        <h2 className="python-output-heading">Згенерований Python</h2>
        <pre className="python-output-code">
          <code>{pythonCode || "// вивід з'явиться тут після компіляції"}</code>
        </pre>
      </section>

      <section className="python-output-section">
        <h2 className="python-output-heading">Результат виконання</h2>
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
