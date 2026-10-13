import { useState } from "react";

const API_BASE = "/api/v1";

function badgeClass(status) {
  if (status === "PASS") return "quality-status pass";
  if (status === "BLOCKED" || status === "NOT_READY") return "quality-status blocked";
  return "quality-status attention";
}

export default function QualityLabPanel({ projectId }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runChecks() {
    if (!projectId || loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(API_BASE + "/projects/" + projectId + "/quality");
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail || "Could not run blueprint checks.");
      setReport(payload);
    } catch (err) {
      setError(err?.message || "Quality check failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="quality-lab-panel" aria-label="Blueprint Quality Lab">
      <div className="quality-lab-head">
        <div>
          <div className="result-label">QUALITY LAB · BLUEPRINT CHECKS</div>
          <h3>Test the engineering blueprint</h3>
          <p>Deterministic checks for traceability, coverage, open questions, and review findings.</p>
        </div>
        <button className="primary-button" onClick={runChecks} disabled={loading || !projectId}>
          {loading ? "Running checks…" : "Run Quality Checks"}
        </button>
      </div>

      {!report && !error && (
        <p className="quality-lab-note">
          These checks validate the saved blueprint. They do not execute generated application code.
        </p>
      )}

      {error && <div className="quality-lab-error" role="alert">{error}</div>}

      {report && (
        <div className="quality-lab-results">
          <div className="quality-lab-summary">
            <span className={badgeClass(report.overall_status)}>{report.overall_status.replace("_", " ")}</span>
            <span>{report.execution_note}</span>
          </div>

          <div className="quality-metric-grid">
            <div className="quality-metric"><strong>{report.metrics.functional_requirements}</strong><span>Requirements</span></div>
            <div className="quality-metric"><strong>{report.metrics.plan_milestones}</strong><span>Milestones</span></div>
            <div className="quality-metric"><strong>{report.metrics.architecture_components}</strong><span>Components</span></div>
            <div className="quality-metric"><strong>{report.metrics.api_capabilities}</strong><span>API capabilities</span></div>
            <div className="quality-metric"><strong>{report.metrics.open_clarifications}</strong><span>Open questions</span></div>
            <div className="quality-metric"><strong>{report.metrics.review_findings}</strong><span>Review findings</span></div>
          </div>

          <div className="quality-coverage-grid">
            {Object.entries(report.metrics.coverage_percentages).map(([key, value]) => (
              <div className="quality-coverage-row" key={key}>
                <div><span>{key.replaceAll("_", " ")}</span><strong>{value}%</strong></div>
                <div className="quality-progress-track"><span style={{ width: value + "%" }} /></div>
              </div>
            ))}
          </div>

          <div className="quality-check-list">
            {report.checks.map((check) => (
              <details className="quality-check" key={check.id}>
                <summary>
                  <span className={badgeClass(check.status)}>{check.status.replace("_", " ")}</span>
                  <strong>{check.title}</strong>
                  <span className="quality-check-summary">{check.summary}</span>
                </summary>
                {check.details.length > 0 && (
                  <ul>{check.details.map((detail, index) => <li key={check.id + "-" + index}>{detail}</li>)}</ul>
                )}
              </details>
            ))}
          </div>

          {report.recommended_actions.length > 0 && (
            <div className="quality-actions">
              <strong>Recommended next actions</strong>
              <ul>{report.recommended_actions.map((action, index) => <li key={index}>{action}</li>)}</ul>
            </div>
          )}
          <div className="quality-lab-note">This result is a blueprint consistency assessment, not a pass result for executable software.</div>
        </div>
      )}
    </section>
  );
}
