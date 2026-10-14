import { useCallback, useEffect, useMemo, useState } from "react";

const TEST_STATUSES = [
  { value: "not_run", label: "Not run" },
  { value: "passed", label: "Passed" },
  { value: "failed", label: "Failed" },
  { value: "blocked", label: "Blocked" },
];

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

export default function ProjectTestingPanel({ projectId, onClose }) {
  const [suite, setSuite] = useState(null);
  const [history, setHistory] = useState([]);
  const [myRole, setMyRole] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [drafts, setDrafts] = useState({});
  const [savingTest, setSavingTest] = useState("");
  const [documentFormat, setDocumentFormat] = useState("pdf");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest(`/api/v1/projects/${projectId}/tests`);
      setSuite(data.suite || null);
      setHistory(data.history || []);
      setMyRole(data.my_role || "");
      setDrafts(
        Object.fromEntries(
          (data.suite?.cases || []).map((testCase) => [
            testCase.test_id,
            {
              status: testCase.status || "not_run",
              execution_notes: testCase.execution_notes || "",
              environment: testCase.environment || "",
            },
          ]),
        ),
      );
    } catch (err) {
      setError(err.message || "Could not load the testing workspace.");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const cases = suite?.cases || [];
  const counts = useMemo(() => {
    const initial = { total: cases.length, passed: 0, failed: 0, blocked: 0, not_run: 0 };
    return cases.reduce((result, testCase) => {
      const status = testCase.status || "not_run";
      result[status] = (result[status] || 0) + 1;
      return result;
    }, initial);
  }, [cases]);

  const canGenerate = ["admin", "owner", "analyst", "tester", "developer"].includes(myRole);
  const canRecordResults = ["admin", "owner", "tester", "developer"].includes(myRole);

  async function generateSuite() {
    setGenerating(true);
    setError("");
    setMessage("");
    try {
      const data = await apiRequest(`/api/v1/projects/${projectId}/tests/generate`, {
        method: "POST",
      });
      setSuite(data.suite || null);
      setHistory((previous) => [
        {
          suite_id: data.suite.suite_id,
          suite_version: data.suite.suite_version,
          project_name: data.suite.project_name,
          summary: data.suite.summary,
          generation_model: data.suite.generation_model,
          created_at: data.suite.created_at,
          case_count: data.suite.cases?.length || 0,
        },
        ...previous.filter((item) => item.suite_id !== data.suite.suite_id),
      ]);
      setDrafts(
        Object.fromEntries(
          (data.suite.cases || []).map((testCase) => [
            testCase.test_id,
            {
              status: testCase.status || "not_run",
              execution_notes: testCase.execution_notes || "",
              environment: testCase.environment || "",
            },
          ]),
        ),
      );
      setMessage("New suite version saved. The generated cases have not been executed.");
    } catch (err) {
      setError(err.message || "Could not generate test cases.");
    } finally {
      setGenerating(false);
    }
  }

  function updateDraft(testId, field, value) {
    setDrafts((previous) => ({
      ...previous,
      [testId]: {
        status: previous[testId]?.status || "not_run",
        execution_notes: previous[testId]?.execution_notes || "",
        environment: previous[testId]?.environment || "",
        [field]: value,
      },
    }));
  }

  async function saveResult(testCase) {
    const draft = drafts[testCase.test_id] || {};
    setSavingTest(testCase.test_id);
    setError("");
    setMessage("");
    try {
      const data = await apiRequest(
        `/api/v1/projects/${projectId}/tests/cases/${testCase.test_id}/result`,
        {
          method: "PATCH",
          body: JSON.stringify({
            status: draft.status || "not_run",
            execution_notes: draft.execution_notes || null,
            environment: draft.environment || null,
          }),
        },
      );
      setSuite(data.suite || null);
      setMessage(`Saved ${testCase.test_id}. Only manually recorded results are counted as executed.`);
    } catch (err) {
      setError(err.message || "Could not save the result.");
    } finally {
      setSavingTest("");
    }
  }

  function downloadUrl(kind) {
    const base = `/api/v1/projects/${encodeURIComponent(projectId)}/documents/${kind}`;
    return kind === "traceability" ? base : `${base}?format=${documentFormat}`;
  }

  const documentFormatLabel = documentFormat === "pdf"
    ? "PDF"
    : documentFormat === "pptx"
      ? "PowerPoint"
      : "Markdown";

  return (
    <section className="testing-workspace-panel">
      <div className="testing-workspace-header">
        <div>
          <div className="auth-eyebrow">QUALITY ENGINEERING</div>
          <h2>Testing & Documents</h2>
          <p>Generate requirement-linked tests, record real execution outcomes, and download engineering documents.</p>
        </div>
        <button className="auth-secondary-button" onClick={onClose}>Close</button>
      </div>

      <div className="testing-export-options">
        <label htmlFor="document-export-format">Download format</label>
        <select
          id="document-export-format"
          value={documentFormat}
          onChange={(event) => setDocumentFormat(event.target.value)}
        >
          <option value="pdf">PDF document (.pdf)</option>
          <option value="pptx">PowerPoint presentation (.pptx)</option>
          <option value="md">Markdown (.md)</option>
        </select>
        <span>Choose the format for SRS, SDD, and test reports. Traceability remains CSV.</span>
      </div>

      <div className="testing-document-grid">
        <a href={downloadUrl("srs")} className="testing-document-link">
          <span className="testing-document-icon">{documentFormat === "pdf" ? "PDF" : documentFormat === "pptx" ? "PPT" : "SRS"}</span>
          <span><strong>Requirements Specification</strong><small>Download {documentFormatLabel}</small></span>
          <span className="testing-download-arrow">↓</span>
        </a>
        <a href={downloadUrl("sdd")} className="testing-document-link">
          <span className="testing-document-icon">{documentFormat === "pdf" ? "PDF" : documentFormat === "pptx" ? "PPT" : "SDD"}</span>
          <span><strong>Design Description</strong><small>Download {documentFormatLabel}</small></span>
          <span className="testing-download-arrow">↓</span>
        </a>
        <a href={downloadUrl("test-report")} className="testing-document-link">
          <span className="testing-document-icon">{documentFormat === "pdf" ? "PDF" : documentFormat === "pptx" ? "PPT" : "QA"}</span>
          <span><strong>Test Report</strong><small>{documentFormatLabel} · recorded results only</small></span>
          <span className="testing-download-arrow">↓</span>
        </a>
        <a href={downloadUrl("traceability")} className="testing-document-link">
          <span className="testing-document-icon">FR</span>
          <span><strong>Traceability Matrix</strong><small>CSV for spreadsheet tools</small></span>
          <span className="testing-download-arrow">↓</span>
        </a>
      </div>

      <div className="testing-suite-toolbar">
        <div>
          <h3>{suite ? `Test Suite v${suite.suite_version}` : "No test suite yet"}</h3>
          <p>
            Project role: <strong>{myRole || "checking…"}</strong>
            {suite?.generation_model ? ` · Model: ${suite.generation_model}` : ""}
          </p>
        </div>
        {canGenerate && (
          <button className="auth-primary-button" onClick={generateSuite} disabled={generating || loading}>
            {generating ? "Designing test cases…" : suite ? "Generate new version" : "Generate with AI"}
          </button>
        )}
      </div>

      <div className="testing-honesty-note">
        <strong>Generated ≠ executed.</strong> AI creates proposed test cases; it does not run your application.
        Only a Tester, Developer, project owner, or admin can record execution results here.
        Actual isolated code execution is a separate upcoming milestone.
      </div>

      {error && <p className="auth-error" role="alert">{error}</p>}
      {message && <p className="auth-success" role="status">{message}</p>}

      {loading ? (
        <div className="testing-empty">Loading test cases…</div>
      ) : !suite ? (
        <div className="testing-empty">
          <strong>No test suite generated yet.</strong>
          <span>Save a requirements artifact first, then use Generate with AI to build a suite linked to FR requirement IDs.</span>
        </div>
      ) : (
        <>
          <div className="testing-metrics">
            <div><strong>{counts.total}</strong><span>Total cases</span></div>
            <div><strong>{suite.requirement_coverage?.length || 0}</strong><span>Requirements covered</span></div>
            <div><strong>{counts.passed + counts.failed + counts.blocked}</strong><span>Marked executed</span></div>
            <div><strong>{counts.failed}</strong><span>Failed results</span></div>
          </div>

          {suite.coverage_warnings?.length > 0 && (
            <div className="testing-warnings">
              <strong>Coverage notes</strong>
              <ul>{suite.coverage_warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
            </div>
          )}

          <div className="testing-case-list">
            {cases.map((testCase) => {
              const draft = drafts[testCase.test_id] || {};
              return (
                <article className="testing-case-card" key={testCase.test_id}>
                  <div className="testing-case-topline">
                    <span className="testing-case-id">{testCase.test_id}</span>
                    <span className={`testing-status-pill status-${testCase.status || "not_run"}`}>
                      {(testCase.status || "not_run").replace("_", " ")}
                    </span>
                    <span className="testing-case-priority">{testCase.priority}</span>
                    <span className="testing-case-type">{testCase.test_type}</span>
                  </div>
                  <h4>{testCase.title}</h4>
                  <p>{testCase.objective}</p>
                  <div className="testing-requirement-ref">
                    <strong>{testCase.requirement_id}</strong>
                    <span>{testCase.requirement_text}</span>
                  </div>

                  {!!testCase.preconditions?.length && (
                    <div className="testing-case-section">
                      <strong>Preconditions</strong>
                      <ul>{testCase.preconditions.map((item, index) => <li key={index}>{item}</li>)}</ul>
                    </div>
                  )}
                  <div className="testing-case-section">
                    <strong>Steps</strong>
                    <ol>{testCase.steps.map((step, index) => <li key={index}>{step}</li>)}</ol>
                  </div>
                  <div className="testing-expected-result">
                    <strong>Expected result</strong>
                    <span>{testCase.expected_result}</span>
                  </div>
                  <div className="testing-case-footer">
                    <span className="testing-generation-source">
                      {testCase.generation_source === "llm" ? "AI-generated" : "Coverage fallback"}
                    </span>
                    {canRecordResults && (
                      <div className="testing-result-form">
                        <label>
                          Actual result status
                          <select
                            value={draft.status || "not_run"}
                            onChange={(event) => updateDraft(testCase.test_id, "status", event.target.value)}
                          >
                            {TEST_STATUSES.map((option) => (
                              <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Environment / build
                          <input
                            value={draft.environment || ""}
                            onChange={(event) => updateDraft(testCase.test_id, "environment", event.target.value)}
                            placeholder="e.g. local dev, build SHA"
                            maxLength={500}
                          />
                        </label>
                        <label className="testing-notes-field">
                          Execution notes / evidence
                          <textarea
                            value={draft.execution_notes || ""}
                            onChange={(event) => updateDraft(testCase.test_id, "execution_notes", event.target.value)}
                            rows={2}
                            maxLength={5000}
                            placeholder="What did you actually observe?"
                          />
                        </label>
                        <button
                          className="auth-secondary-button"
                          onClick={() => saveResult(testCase)}
                          disabled={savingTest === testCase.test_id}
                        >
                          {savingTest === testCase.test_id ? "Saving…" : "Save result"}
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </>
      )}

      <div className="testing-history">
        <h3>Test suite history</h3>
        {history.length === 0 ? (
          <p>No versions created yet.</p>
        ) : (
          <div className="testing-history-list">
            {history.map((item) => (
              <div key={item.suite_id} className="testing-history-item">
                <strong>v{item.suite_version}</strong>
                <span>{item.case_count} cases</span>
                <span>{item.generation_model || "Model not recorded"}</span>
                <time>{new Date(item.created_at).toLocaleString()}</time>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
