import { useEffect, useMemo, useState } from "react";

const API_BASE = "/api/v1";

const AGENT_CONFIG = [
  {
    key: "requirements",
    label: "Requirements",
    subtitle: "Requirement Analyst",
    icon: "01",
  },
  {
    key: "project_plan",
    label: "Project Plan",
    subtitle: "Planning Agent",
    icon: "02",
  },
  {
    key: "architecture",
    label: "Architecture",
    subtitle: "Software Architect",
    icon: "03",
  },
  {
    key: "review",
    label: "Technical Review",
    subtitle: "Technical Reviewer",
    icon: "04",
  },
];

const DEFAULT_IDEA =
  "Build an online food delivery platform where customers can discover restaurants, browse menus, place orders, make payments, and track deliveries.";

function App() {
  const [idea, setIdea] = useState("");
  const [project, setProject] = useState(null);
  const [artifacts, setArtifacts] = useState(null);
  const [activeArtifact, setActiveArtifact] = useState("requirements");
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState("");

  const isRunning = project?.status === "running";

  const activeData = useMemo(() => {
    if (!artifacts) {
      return null;
    }

    return artifacts[activeArtifact] ?? null;
  }, [artifacts, activeArtifact]);

  async function createProject() {
    const trimmedIdea = idea.trim();

    if (!trimmedIdea) {
      setError("Please enter a software idea first.");
      return null;
    }

    setError("");
    setArtifacts(null);
    setActiveArtifact("requirements");

    const response = await fetch(
      `${API_BASE}/projects`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          idea: trimmedIdea,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail || "Could not create project."
      );
    }

    setProject(data);

    return data;
  }

  async function fetchProject(projectId) {
    const response = await fetch(
      `${API_BASE}/projects/${projectId}`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail || "Could not fetch project."
      );
    }

    setProject(data);

    return data;
  }

  async function fetchArtifacts(projectId) {
    const response = await fetch(
      `${API_BASE}/projects/${projectId}/artifacts`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail || "Could not fetch project artifacts."
      );
    }

    setArtifacts(data);

    return data;
  }

  async function runWorkflow(projectId) {
    const response = await fetch(
      `${API_BASE}/projects/${projectId}/run`,
      {
        method: "POST",
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail || "Project workflow failed."
      );
    }

    return data;
  }

  async function handleBuild() {
    if (loading) {
      return;
    }

    setLoading(true);
    setError("");
    setArtifacts(null);
    setStatusMessage(
      "Creating your project..."
    );

    try {
      const created = await createProject();

      if (!created) {
        return;
      }

      setStatusMessage(
        "AI team is analyzing your project..."
      );

      const runPromise = runWorkflow(
        created.project_id
      );

      await new Promise((resolve) => {
        setTimeout(resolve, 300);
      });

      let finished = false;

      while (!finished) {
        const latest = await fetchProject(
          created.project_id
        );

        if (
          latest.status === "completed"
          || latest.status === "failed"
        ) {
          finished = true;

          if (latest.status === "failed") {
            throw new Error(
              latest.error ||
              "Project workflow failed."
            );
          }
        } else {
          setStatusMessage(
            "AI team is working through requirements, planning, architecture, and review..."
          );

          await new Promise((resolve) => {
            setTimeout(resolve, 2500);
          });
        }
      }

      await runPromise;

      setStatusMessage(
        "Project blueprint completed."
      );

      await fetchArtifacts(
        created.project_id
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong."
      );

      setStatusMessage("");
    } finally {
      setLoading(false);
    }
  }

  function loadDemoIdea() {
    setIdea(DEFAULT_IDEA);
    setError("");
  }

  function clearProject() {
    setProject(null);
    setArtifacts(null);
    setActiveArtifact("requirements");
    setStatusMessage("");
    setError("");
  }

  useEffect(() => {
    if (!project?.project_id) {
      return;
    }

    if (
      project.status === "completed"
      || project.status === "failed"
    ) {
      return;
    }
  }, [project]);

  const projectName =
    artifacts?.project_name ||
    project?.project_name ||
    "New Project";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            AD
          </div>

          <div>
            <div className="brand-name">
              AI Development Studio
            </div>

            <div className="brand-subtitle">
              Multi-Agent Software Engineering
            </div>
          </div>
        </div>

        <div className="topbar-meta">
          <div className="status-dot">
            <span />
            Local AI
          </div>

          {project && (
            <button
              className="ghost-button"
              onClick={clearProject}
            >
              New Project
            </button>
          )}
        </div>
      </header>

      <main className="main-content">
        <section className="hero-section">
          <div className="eyebrow">
            AI-POWERED SOFTWARE ENGINEERING
          </div>

          <h1>
            Turn an idea into a
            <span> technical blueprint.</span>
          </h1>

          <p className="hero-copy">
            Describe what you want to build.
            Our AI engineering pipeline transforms
            it into requirements, a project plan,
            system architecture, and a technical
            review.
          </p>

          {!artifacts && (
            <div className="idea-card">
              <div className="input-header">
                <div>
                  <div className="input-label">
                    What do you want to build?
                  </div>

                  <div className="input-hint">
                    Describe the product, platform,
                    application, or system in natural language.
                  </div>
                </div>

                <button
                  className="demo-button"
                  onClick={loadDemoIdea}
                  disabled={loading}
                >
                  Load demo idea
                </button>
              </div>

              <textarea
                value={idea}
                onChange={(event) =>
                  setIdea(event.target.value)
                }
                placeholder="Example: Build a college learning management system where students can access courses and materials, submit assignments, view grades and receive notifications..."
                disabled={loading}
              />

              <div className="input-footer">
                <div className="input-counter">
                  {idea.length} characters
                </div>

                <button
                  className="primary-button"
                  onClick={handleBuild}
                  disabled={
                    loading ||
                    !idea.trim()
                  }
                >
                  {loading ? (
                    <>
                      <span className="button-spinner" />
                      Building...
                    </>
                  ) : (
                    <>
                      Run All
                      <span className="arrow">
                        →
                      </span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {loading && (
            <div className="run-state">
              <div className="run-state-left">
                <div className="pulse-orb" />

                <div>
                  <div className="run-title">
                    {statusMessage}
                  </div>

                  <div className="run-description">
                    This may take a few minutes on
                    CPU-only local inference.
                  </div>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="error-box">
              <div className="error-title">
                Workflow error
              </div>

              <div className="error-message">
                {error}
              </div>
            </div>
          )}
        </section>

        {artifacts && (
          <section className="workspace">
            <div className="workspace-header">
              <div>
                <div className="workspace-eyebrow">
                  PROJECT WORKSPACE
                </div>

                <h2>{projectName}</h2>

                <div className="workspace-meta">
                  <span className="approved-badge">
                    <span className="badge-check">
                      ✓
                    </span>
                    Approved
                  </span>

                  <span>
                    Project ID:{" "}
                    {project?.project_id}
                  </span>
                </div>
              </div>

              <div className="workspace-actions">
                <button
                  className="secondary-button"
                  onClick={() =>
                    fetchArtifacts(
                      project.project_id
                    )
                  }
                >
                  Refresh
                </button>
              </div>
            </div>

            <div className="agent-grid">
              {AGENT_CONFIG.map((agent) => {
                const isActive =
                  activeArtifact === agent.key;

                return (
                  <button
                    key={agent.key}
                    className={
                      isActive
                        ? "agent-card active"
                        : "agent-card"
                    }
                    onClick={() =>
                      setActiveArtifact(
                        agent.key
                      )
                    }
                  >
                    <div className="agent-number">
                      {agent.icon}
                    </div>

                    <div className="agent-info">
                      <div className="agent-label">
                        {agent.label}
                      </div>

                      <div className="agent-subtitle">
                        {agent.subtitle}
                      </div>
                    </div>

                    <div className="agent-check">
                      ✓
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="artifact-layout">
              <aside className="artifact-sidebar">
                <div className="sidebar-title">
                  Artifacts
                </div>

                {AGENT_CONFIG.map((agent) => (
                  <button
                    key={agent.key}
                    className={
                      activeArtifact === agent.key
                        ? "artifact-nav active"
                        : "artifact-nav"
                    }
                    onClick={() =>
                      setActiveArtifact(
                        agent.key
                      )
                    }
                  >
                    <span>
                      {agent.label}
                    </span>

                    <span className="nav-arrow">
                      →
                    </span>
                  </button>
                ))}

                <div className="sidebar-divider" />

                <div className="sidebar-note">
                  <div className="sidebar-note-title">
                    Traceability
                  </div>

                  <div className="sidebar-note-copy">
                    Requirements are linked through
                    the plan, architecture, APIs, and
                    technical review.
                  </div>
                </div>
              </aside>

              <section className="artifact-panel">
                <div className="artifact-header">
                  <div>
                    <div className="artifact-kicker">
                      {AGENT_CONFIG.find(
                        (item) =>
                          item.key ===
                          activeArtifact
                      )?.subtitle}
                    </div>

                    <h3>
                      {AGENT_CONFIG.find(
                        (item) =>
                          item.key ===
                          activeArtifact
                      )?.label}
                    </h3>
                  </div>

                  <div className="artifact-status">
                    Completed
                  </div>
                </div>

                <div className="json-viewer">
                  <pre>
                    {JSON.stringify(
                      activeData,
                      null,
                      2
                    )}
                  </pre>
                </div>
              </section>
            </div>
          </section>
        )}

        <section className="pipeline-section">
          <div className="pipeline-header">
            <div>
              <div className="pipeline-eyebrow">
                PIPELINE
              </div>

              <h2>
                One idea. Four engineering stages.
              </h2>
            </div>

            <div className="pipeline-status">
              Local multi-agent workflow
            </div>
          </div>

          <div className="pipeline">
            {AGENT_CONFIG.map((agent, index) => (
              <div
                className="pipeline-item"
                key={agent.key}
              >
                <div className="pipeline-step">
                  <span>
                    {agent.icon}
                  </span>
                </div>

                <div className="pipeline-copy">
                  <div className="pipeline-title">
                    {agent.label}
                  </div>

                  <div className="pipeline-description">
                    {index === 0 &&
                      "Extract the software requirements."}

                    {index === 1 &&
                      "Organize the work into milestones and tasks."}

                    {index === 2 &&
                      "Transform requirements into system architecture."}

                    {index === 3 &&
                      "Audit coverage, traceability, and consistency."}
                  </div>
                </div>

                {index <
                  AGENT_CONFIG.length - 1 && (
                  <div className="pipeline-line" />
                )}
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="footer">
        <div>
          AI Development Studio
        </div>

        <div>
          Local AI • FastAPI • React
        </div>
      </footer>
    </div>
  );
}

export default App;