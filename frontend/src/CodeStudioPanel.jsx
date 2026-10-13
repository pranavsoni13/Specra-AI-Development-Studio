import { useCallback, useEffect, useMemo, useState } from "react";

async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed (${response.status}).`);
  }
  return payload;
}

export default function CodeStudioPanel({ projectId, onClose }) {
  const [history, setHistory] = useState([]);
  const [bundle, setBundle] = useState(null);
  const [myRole, setMyRole] = useState("");
  const [canGenerate, setCanGenerate] = useState(false);
  const [constraints, setConstraints] = useState("");
  const [selectedPath, setSelectedPath] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const baseUrl = `/api/v1/projects/${encodeURIComponent(projectId)}/code-bundles`;
  const files = bundle?.files || [];
  const selectedFile = useMemo(
    () => files.find((file) => file.path === selectedPath) || files[0] || null,
    [files, selectedPath],
  );

  const loadBundle = useCallback(async (bundleId) => {
    const result = await apiRequest(`${baseUrl}/${encodeURIComponent(bundleId)}`);
    setBundle(result.bundle || null);
    setSelectedPath(result.bundle?.files?.[0]?.path || "");
  }, [baseUrl]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await apiRequest(baseUrl);
      setHistory(result.bundles || []);
      setMyRole(result.my_role || "");
      setCanGenerate(Boolean(result.can_generate));
      if (result.bundles?.length) {
        await loadBundle(result.bundles[0].bundle_id);
      } else {
        setBundle(null);
      }
    } catch (err) {
      setError(err.message || "Could not load Code Studio.");
    } finally {
      setLoading(false);
    }
  }, [baseUrl, loadBundle]);

  useEffect(() => {
    load();
  }, [load]);

  async function generate() {
    setGenerating(true);
    setError("");
    setMessage("");
    try {
      const result = await apiRequest(`${baseUrl}/generate`, {
        method: "POST",
        body: JSON.stringify({
          stack: "fastapi-react",
          additional_constraints: constraints,
        }),
      });
      const metadata = result.bundle;
      setMessage(
        `Code bundle v${metadata.bundle_version} saved. It has not been executed; review it in VS Code and run its tests.`,
      );
      await loadBundle(metadata.bundle_id);
      const refreshed = await apiRequest(baseUrl);
      setHistory(refreshed.bundles || []);
      setMyRole(refreshed.my_role || "");
      setCanGenerate(Boolean(refreshed.can_generate));
    } catch (err) {
      setError(err.message || "Could not generate the code bundle.");
    } finally {
      setGenerating(false);
    }
  }

  function downloadUrl(bundleId) {
    return `${baseUrl}/${encodeURIComponent(bundleId)}/download`;
  }

  return (
    <section className="code-studio-panel">
      <div className="code-studio-header">
        <div className="code-studio-brand">
          <div className="code-studio-mark">&lt;/&gt;</div>
          <div>
            <div className="auth-eyebrow">BLUEPRINT → CODE</div>
            <h2>Code Studio · Visual Studio Code</h2>
            <p>Generate a versioned React + FastAPI starter bundle from your reviewed project blueprint.</p>
          </div>
        </div>
        <button className="auth-secondary-button" onClick={onClose}>Close</button>
      </div>

      <div className="code-studio-notice">
        <strong>Export, review, run.</strong> Specra creates source files and trusted VS Code launch/tasks configuration.
        It does not execute generated source inside the Specra API process. Download the ZIP, open the folder in VS Code,
        inspect the diff, install dependencies, run the included smoke tests, and add project-specific tests before deployment.
      </div>

      <div className="code-studio-controls">
        <label>
          Extra implementation constraints (optional)
          <textarea
            value={constraints}
            onChange={(event) => setConstraints(event.target.value)}
            placeholder="e.g. Keep dependencies minimal, use SQLite for the prototype, include accessibility and error states…"
            rows={3}
            maxLength={5000}
            disabled={generating}
          />
        </label>
        <div className="code-studio-generate-row">
          <div>
            <span className="auth-role-chip">{myRole || "checking role"}</span>
            <p>Requires saved requirements, plan, architecture, and a passing technical review.</p>
          </div>
          {canGenerate && (
            <button className="auth-primary-button" onClick={generate} disabled={generating || loading}>
              {generating ? "Generating project files…" : history.length ? "Generate new code version" : "Generate VS Code project"}
            </button>
          )}
        </div>
      </div>

      {error && <p className="auth-error" role="alert">{error}</p>}
      {message && <p className="auth-success" role="status">{message}</p>}

      {loading ? (
        <div className="code-studio-empty">Loading code bundle history…</div>
      ) : !history.length || !bundle ? (
        <div className="code-studio-empty">
          <strong>No code bundle generated yet.</strong>
          <span>Run the engineering workflow and get a passing technical review first. Code generation then produces a ZIP with VS Code tasks and a backend smoke-test scaffold.</span>
        </div>
      ) : (
        <>
          <div className="code-studio-bundle-summary">
            <div>
              <div className="code-studio-version">BUNDLE v{bundle.bundle_version} · {bundle.stack}</div>
              <h3>{bundle.project_name}</h3>
              <p>{bundle.summary}</p>
              <div className="code-studio-statuses">
                <span className={`code-status ${bundle.validation_status === "static_checks_clear" ? "code-status-review" : "code-status-warning"}`}>
                  {bundle.validation_status.replaceAll("_", " ")}
                </span>
                <span className="code-status code-status-unrun">execution: {bundle.execution_status.replaceAll("_", " ")}</span>
                <span className="code-status">{files.length} files</span>
              </div>
            </div>
            <a
              className="code-studio-download"
              href={downloadUrl(bundle.bundle_id)}
              download
            >
              Download ZIP ↓
            </a>
          </div>

          {bundle.validation_warnings?.length > 0 && (
            <div className="code-studio-warnings">
              <strong>Review before running</strong>
              <ul>{bundle.validation_warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
            </div>
          )}

          <div className="code-studio-explorer">
            <aside className="code-studio-file-tree">
              <div className="code-studio-tree-title">SOURCE FILES</div>
              {files.map((file) => (
                <button
                  className={`code-studio-file ${selectedFile?.path === file.path ? "active" : ""}`}
                  key={file.path}
                  onClick={() => setSelectedPath(file.path)}
                  title={file.purpose}
                >
                  <span className="code-file-icon">{file.path.split(".").pop()?.toUpperCase().slice(0, 3) || "FILE"}</span>
                  <span>{file.path}</span>
                </button>
              ))}
            </aside>
            <div className="code-studio-preview">
              {selectedFile ? (
                <>
                  <div className="code-studio-preview-header">
                    <div>
                      <strong>{selectedFile.path}</strong>
                      <span>{selectedFile.purpose}</span>
                    </div>
                    <span>{selectedFile.content.length.toLocaleString()} chars</span>
                  </div>
                  <pre><code>{selectedFile.content}</code></pre>
                </>
              ) : (
                <div className="code-studio-empty">Choose a source file to preview it.</div>
              )}
            </div>
          </div>

          <div className="code-studio-setup-grid">
            <div>
              <h4>Setup notes</h4>
              <ol>{(bundle.setup_notes || []).map((note, index) => <li key={index}>{note}</li>)}</ol>
            </div>
            <div>
              <h4>Test notes</h4>
              <ol>{(bundle.test_notes || []).map((note, index) => <li key={index}>{note}</li>)}</ol>
            </div>
          </div>

          <div className="code-studio-history">
            <h4>Bundle history</h4>
            {history.map((item) => (
              <button
                key={item.bundle_id}
                className={`code-studio-history-item ${item.bundle_id === bundle.bundle_id ? "active" : ""}`}
                onClick={() => loadBundle(item.bundle_id).catch((err) => setError(err.message))}
              >
                <strong>v{item.bundle_version}</strong>
                <span>{item.file_count} files</span>
                <span>{item.validation_status.replaceAll("_", " ")}</span>
                <span>{new Date(item.created_at).toLocaleString()}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
