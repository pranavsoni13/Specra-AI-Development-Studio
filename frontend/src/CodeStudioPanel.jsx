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
  const [generationReady, setGenerationReady] = useState(false);
  const [generationBlockReason, setGenerationBlockReason] = useState("");
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
      setGenerationReady(Boolean(result.generation_ready));
      setGenerationBlockReason(result.generation_block_reason || "");
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
      const generatedFileCount = metadata.files?.length || 0;
      setMessage(
        `Code bundle v${metadata.bundle_version} saved with ${generatedFileCount} source files. Preview them below or download the ZIP. Generated code has not been executed; review it and run its tests before deployment.`,
      );
      await loadBundle(metadata.bundle_id);
      const refreshed = await apiRequest(baseUrl);
      setHistory(refreshed.bundles || []);
      setMyRole(refreshed.my_role || "");
      setCanGenerate(Boolean(refreshed.can_generate));
      setGenerationReady(Boolean(refreshed.generation_ready));
      setGenerationBlockReason(refreshed.generation_block_reason || "");
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
            <p>Generate real project-specific React + FastAPI source files from your reviewed blueprint, preview each file, and download the complete project ZIP.</p>
          </div>
        </div>
        <button className="auth-secondary-button" onClick={onClose}>Close</button>
      </div>

      <div className="code-studio-notice">
        <strong>Generate files, preview, export.</strong> The coding model writes project-specific API routes, domain logic,
        React screens, and supporting files. Every generated file appears in the source tree and can be previewed below.
        Download the ZIP to get the actual folder and files on your device. Specra does not execute generated source inside
        the API process; review it and run tests before deployment.
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
            <button
              className="auth-primary-button"
              onClick={generate}
              disabled={generating || loading || !generationReady}
              title={generationBlockReason || "Generate project-specific source files"}
            >
              {generating
                ? "Generating project files…"
                : !generationReady
                  ? "Complete blueprint to enable generation"
                  : history.length
                    ? "Generate new code version"
                    : "Generate VS Code project"}
            </button>
          )}
        </div>
      </div>

      {!loading && canGenerate && generationBlockReason && (
        <div className="code-studio-access-note" role="status">
          <strong>{canGenerate ? "Generation not ready yet" : "Code generation access"}</strong>
          <span>{generationBlockReason}</span>
        </div>
      )}

      {!loading && !canGenerate && (
        <div className="code-studio-access-note" role="note">
          <strong>Read-only Code Studio</strong>
          <span>Your role can view and download existing bundles, but cannot generate new source code. Ask the project administrator for an Analyst, Architect, Developer, or Owner role.</span>
        </div>
      )}

      {error && <p className="auth-error" role="alert">{error}</p>}
      {message && <p className="auth-success" role="status">{message}</p>}

      {loading ? (
        <div className="code-studio-empty">Loading code bundle history…</div>
      ) : !history.length || !bundle ? (
        <div className="code-studio-empty">
          <strong>No code bundle generated yet.</strong>
          <span>Complete the requirements, project plan, architecture, and passing technical review first. Then generate a project-specific React interface and FastAPI implementation. The generated files will appear here for preview and ZIP download.</span>
        </div>
      ) : (
        <>
          <div className="code-studio-bundle-summary">
            <div>
              <div className="code-studio-version">BUNDLE v{bundle.bundle_version} · {bundle.stack} · {files.length} SOURCE FILES</div>
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
