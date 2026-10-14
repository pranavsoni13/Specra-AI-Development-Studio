import { useEffect, useMemo, useState } from "react";
import ProjectMemoryPanel from "./components/ProjectMemoryPanel";
import ProjectTeamPanel from "./ProjectTeamPanel";
import ProjectTestingPanel from "./ProjectTestingPanel";
import ProjectCopilotPanel from "./ProjectCopilotPanel";
import CodeStudioPanel from "./CodeStudioPanel";
import QualityLabPanel from "./components/QualityLabPanel";

const API_BASE = "/api/v1";

const AGENT_CONFIG = [
  {
    key: "requirements",
    stage: "requirements",
    label: "Requirements",
    subtitle: "Requirement Analyst",
    icon: "01",
    actionLabel: "Ask Requirement Analyst",
  },
  {
    key: "project_plan",
    stage: "project_plan",
    label: "Project Plan",
    subtitle: "Planning Agent",
    icon: "02",
    actionLabel: "Ask Planning Agent",
  },
  {
    key: "architecture",
    stage: "architecture",
    label: "Architecture",
    subtitle: "Software Architect",
    icon: "03",
    actionLabel: "Ask Software Architect",
  },
  {
    key: "review",
    stage: "technical_review",
    label: "Technical Review",
    subtitle: "Technical Reviewer",
    icon: "04",
    actionLabel: "Ask Technical Reviewer",
  },
];

const STAGE_LABELS = {
  requirements: "Requirements",
  project_plan: "Project Plan",
  architecture: "Architecture",
  technical_review: "Technical Review",
  completed: "Completed",
};

const DEFAULT_IDEA =
  "Build an online food delivery platform where customers can discover restaurants, browse menus, place orders, make payments, and track deliveries.";

const VALID_ARTIFACT_KEYS = new Set(["requirements", "project_plan", "architecture", "review"]);

function safeStorageRead(key) {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function safeStorageWrite(key, value) {
  try { window.localStorage.setItem(key, value); } catch { /* storage may be unavailable */ }
}
function safeStorageRemove(key) {
  try { window.localStorage.removeItem(key); } catch { /* storage may be unavailable */ }
}
function restoreScrollPosition(projectId) {
  const raw = safeStorageRead(`specra:scroll:${projectId}`);
  if (raw === null) return;
  const scrollY = Number(raw);
  if (!Number.isFinite(scrollY) || scrollY < 0) return;
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
    window.scrollTo({ top: scrollY, left: 0, behavior: "auto" });
  }));
}

function App({ currentUser }) {
  const [idea, setIdea] = useState("");
  const [project, setProject] = useState(null);
  const [projects, setProjects] = useState([]);
  const [artifacts, setArtifacts] = useState(null);

  const [activeArtifact, setActiveArtifact] =
    useState("requirements");

  const [loading, setLoading] = useState(false);
  const [refining, setRefining] = useState(false);

  const [statusMessage, setStatusMessage] =
    useState("");

  const [error, setError] = useState("");

  const [showJson, setShowJson] =
    useState(false);

  const [showProjects, setShowProjects] =
    useState(false);

  const [showVersions, setShowVersions] =
    useState(false);

  const [showEvents, setShowEvents] =
    useState(false);

  const [showMemory, setShowMemory] = useState(false);
  const [showTeam, setShowTeam] = useState(false);
  const [showTesting, setShowTesting] = useState(false);
  const [showCopilot, setShowCopilot] = useState(false);
  const [showCodeStudio, setShowCodeStudio] = useState(false);
  const [workspaceReady, setWorkspaceReady] = useState(false);

  const [versions, setVersions] =
    useState({});

  const [selectedVersion, setSelectedVersion] =
    useState(null);

  const [
    selectedCompareVersion,
    setSelectedCompareVersion,
  ] = useState(null);

  const [events, setEvents] =
    useState([]);

  const [refinementMode, setRefinementMode] =
    useState(null);

  const [
    refinementInstruction,
    setRefinementInstruction,
  ] = useState("");

  const activeData = useMemo(() => {
    if (!artifacts) {
      return null;
    }

    return (
      artifacts[activeArtifact] ??
      null
    );
  }, [
    artifacts,
    activeArtifact,
  ]);

  function getStageState(agent) {
    if (!project) {
      return "waiting";
    }

    const backendState =
      project.stages?.[agent.stage];

    const hasArtifact = Boolean(
      artifacts?.[agent.key]
    );

    if (
      backendState === "waiting" &&
      hasArtifact
    ) {
      return "stale";
    }

    if (backendState) {
      return backendState;
    }

    if (project.status === "completed") {
      return "completed";
    }

    if (
      project.current_stage ===
      agent.stage
    ) {
      return project.stage_status;
    }

    return "waiting";
  }

  function statusLabel(state) {
    if (state === "completed") {
      return "Completed";
    }

    if (state === "running") {
      return "Running";
    }

    if (state === "queued") {
      return "Queued";
    }

    if (state === "failed") {
      return "Failed";
    }

    if (state === "interrupted") {
      return "Interrupted";
    }

    if (state === "stale") {
      return "Stale";
    }

    return "Waiting";
  }

  function getStatusMessage(
    currentProject
  ) {
    if (!currentProject) {
      return "";
    }

    if (
      currentProject.status ===
      "failed"
    ) {
      return (
        currentProject.error ||
        "The workflow encountered an error."
      );
    }

    if (
      currentProject.status ===
      "interrupted"
    ) {
      return "Workflow was interrupted by a backend restart.";
    }

    if (
      currentProject.status ===
      "completed"
    ) {
      return "Project operation completed.";
    }

    const label =
      STAGE_LABELS[
        currentProject.current_stage
      ] ||
      "AI workflow";

    if (
      currentProject.stage_status ===
      "queued"
    ) {
      return `${label} is queued...`;
    }

    return `${label} is being generated...`;
  }

  async function fetchProjects() {
    const response =
      await fetch(
        `${API_BASE}/projects`
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail ||
          "Could not load projects."
      );
    }

    setProjects(data);

    return data;
  }

  async function fetchProject(
    projectId
  ) {
    const response =
      await fetch(
        `${API_BASE}/projects/${projectId}`
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail ||
          "Could not fetch project."
      );
    }

    setProject(data);
    safeStorageWrite("specra:lastProjectId", projectId);

    return data;
  }

  async function fetchArtifacts(
    projectId
  ) {
    const response =
      await fetch(
        `${API_BASE}/projects/${projectId}/artifacts`
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail ||
          "Could not fetch artifacts."
      );
    }

    setArtifacts({
      project_name:
        data.project_name,
      requirements:
        data.requirements,
      project_plan:
        data.project_plan,
      architecture:
        data.architecture,
      review:
        data.review,
    });

    return data;
  }

  async function fetchVersions(
    projectId
  ) {
    const response =
      await fetch(
        `${API_BASE}/projects/${projectId}/versions`
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail ||
          "Could not load version history."
      );
    }

    setVersions(data);

    return data;
  }

  async function fetchEvents(
    projectId
  ) {
    const response =
      await fetch(
        `${API_BASE}/projects/${projectId}/events?limit=100`
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail ||
          "Could not load project events."
      );
    }

    setEvents(data);

    return data;
  }


  function getArtifactVersion(
    agentKey
  ) {
    const stage =
      agentKey === "review"
        ? "technical_review"
        : agentKey;

    return (
      project?.artifact_versions?.[stage] ||
      0
    );
  }

  function getStaleAgents() {
    return AGENT_CONFIG.filter(
      (agent) =>
        getStageState(agent) ===
        "stale"
    );
  }

  async function rebuildFromStage(
    agentKey
  ) {
    if (
      !project?.project_id ||
      loading ||
      refining
    ) {
      return;
    }

    const agent =
      AGENT_CONFIG.find(
        (item) =>
          item.key === agentKey
      );

    if (!agent) {
      return;
    }

    const instruction = `Rebuild the ${agent.label} artifact from the latest authoritative upstream artifacts. Preserve valid existing decisions where possible, resolve all stale dependencies, and return a complete internally consistent artifact. Do not invent unrelated functionality.`;

    setRefining(true);
    setError("");
    setShowJson(false);
    setShowVersions(false);

    try {
      const response =
        await fetch(
          `${API_BASE}/projects/${project.project_id}/artifacts/${agent.stage}/regenerate`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              instruction,
            }),
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            `Could not rebuild ${agent.label}.`
        );
      }

      setProject(data);

      await waitForProjectCompletion(
        project.project_id,
        (latest) => {
          if (
            latest.status ===
            "completed"
          ) {
            return `${agent.label} and affected downstream artifacts completed.`;
          }

          return getStatusMessage(
            latest
          );
        }
      );

      setStatusMessage(
        `${agent.label} rebuilt and downstream artifacts refreshed.`
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : `Could not rebuild ${agent.label}.`
      );

      setStatusMessage("");
    } finally {
      setRefining(false);
    }
  }

  function flattenValue(
    value,
    path = "",
    output = []
  ) {
    if (
      value === null ||
      typeof value !== "object"
    ) {
      output.push({
        path: path || "value",
        value,
      });

      return output;
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        output.push({
          path: path || "value",
          value: [],
        });

        return output;
      }

      value.forEach(
        (item, index) => {
          flattenValue(
            item,
            path
              ? `${path}[${index}]`
              : `[${index}]`,
            output
          );
        }
      );

      return output;
    }

    const keys =
      Object.keys(value);

    if (keys.length === 0) {
      output.push({
        path: path || "value",
        value: {},
      });

      return output;
    }

    keys.forEach((key) => {
      flattenValue(
        value[key],
        path
          ? `${path}.${key}`
          : key,
        output
      );
    });

    return output;
  }

  function buildHumanDiff(
    older,
    newer
  ) {
    const olderEntries =
      flattenValue(
        older || {}
      );

    const newerEntries =
      flattenValue(
        newer || {}
      );

    const olderMap =
      new Map(
        olderEntries.map(
          (entry) => [
            entry.path,
            entry.value,
          ]
        )
      );

    const newerMap =
      new Map(
        newerEntries.map(
          (entry) => [
            entry.path,
            entry.value,
          ]
        )
      );

    const paths = Array.from(
      new Set([
        ...olderMap.keys(),
        ...newerMap.keys(),
      ])
    ).sort();

    return paths
      .map((path) => {
        const hasOld =
          olderMap.has(path);

        const hasNew =
          newerMap.has(path);

        if (
          !hasOld &&
          hasNew
        ) {
          return {
            kind: "added",
            path,
            before: undefined,
            after:
              newerMap.get(
                path
              ),
          };
        }

        if (
          hasOld &&
          !hasNew
        ) {
          return {
            kind: "removed",
            path,
            before:
              olderMap.get(
                path
              ),
            after: undefined,
          };
        }

        const before =
          olderMap.get(path);

        const after =
          newerMap.get(path);

        if (
          JSON.stringify(
            before
          ) !==
          JSON.stringify(
            after
          )
        ) {
          return {
            kind: "changed",
            path,
            before,
            after,
          };
        }

        return null;
      })
      .filter(Boolean);
  }

  function formatDiffValue(
    value
  ) {
    if (
      value === undefined
    ) {
      return "—";
    }

    if (
      typeof value ===
        "string"
    ) {
      return value;
    }

    return JSON.stringify(
      value
    );
  }

  function selectVersionForComparison(
    versionNumber
  ) {
    setSelectedVersion(
      versionNumber
    );

    const candidates =
      versionList.filter(
        (version) =>
          version.version_number !==
          versionNumber
      );

    if (
      candidates.length ===
      0
    ) {
      setSelectedCompareVersion(
        null
      );
      return;
    }

    const previous =
      candidates.find(
        (version) =>
          version.version_number ===
          versionNumber - 1
      );

    setSelectedCompareVersion(
      previous
        ? previous.version_number
        : candidates[0]
            .version_number
    );
  }

  async function createProject() {
    const trimmedIdea =
      idea.trim();

    if (!trimmedIdea) {
      setError(
        "Please enter a software idea first."
      );

      return null;
    }

    const response =
      await fetch(
        `${API_BASE}/projects`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            idea: trimmedIdea,
          }),
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail ||
          "Could not create project."
      );
    }

    setProject(data);
    safeStorageWrite("specra:lastProjectId", data.project_id);
    setWorkspaceReady(true);
    setShowMemory(false);
    setArtifacts(null);
    setVersions({});
    setEvents([]);
    setActiveArtifact("requirements");

    await fetchProjects();

    return data;
  }

  async function startFullWorkflow(
    projectId
  ) {
    const response =
      await fetch(
        `${API_BASE}/projects/${projectId}/run`,
        {
          method: "POST",
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail ||
          "Could not start workflow."
      );
    }

    setProject(data);

    return data;
  }

  async function waitForProjectCompletion(
    projectId,
    messageBuilder
  ) {
    let latest =
      await fetchProject(
        projectId
      );

    setStatusMessage(
      messageBuilder
        ? messageBuilder(latest)
        : getStatusMessage(latest)
    );

    while (
      latest.status !==
        "completed" &&
      latest.status !==
        "failed" &&
      latest.status !==
        "interrupted"
    ) {
      await new Promise(
        (resolve) =>
          setTimeout(
            resolve,
            1500
          )
      );

      latest =
        await fetchProject(
          projectId
        );

      await fetchArtifacts(
        projectId
      );

      if (messageBuilder) {
        setStatusMessage(
          messageBuilder(
            latest
          )
        );
      } else {
        setStatusMessage(
          getStatusMessage(
            latest
          )
        );
      }
    }

    await fetchArtifacts(
      projectId
    );

    await fetchVersions(
      projectId
    );

    await fetchEvents(
      projectId
    );

    await fetchProjects();

    if (
      latest.status ===
      "failed"
    ) {
      throw new Error(
        latest.error ||
          "The project operation failed."
      );
    }

    if (
      latest.status ===
      "interrupted"
    ) {
      throw new Error(
        "The previous workflow was interrupted by a backend restart."
      );
    }

    return latest;
  }

  async function handleBuild() {
    if (
      loading ||
      refining
    ) {
      return;
    }

    setLoading(true);
    setError("");
    setArtifacts(null);
    setShowJson(false);

    try {
      const created =
        await createProject();

      if (!created) {
        return;
      }

      await startFullWorkflow(
        created.project_id
      );

      await waitForProjectCompletion(
        created.project_id
      );

      setStatusMessage(
        "Project blueprint completed."
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

  async function submitRefinement() {
    const instruction =
      refinementInstruction.trim();

    if (!instruction) {
      setError(
        "Write what you want changed first."
      );

      return;
    }

    if (
      !project?.project_id
    ) {
      return;
    }

    if (
      loading ||
      refining
    ) {
      return;
    }

    const isGlobal =
      refinementMode ===
      "global";

    const agent =
      AGENT_CONFIG.find(
        (item) =>
          item.key ===
          refinementMode
      );

    const backendStage =
      isGlobal
        ? null
        : agent?.stage;

    setRefining(true);
    setError("");
    setShowJson(false);

    try {
      const endpoint =
        isGlobal
          ? `${API_BASE}/projects/${project.project_id}/refine`
          : `${API_BASE}/projects/${project.project_id}/artifacts/${backendStage}/regenerate`;

      const response =
        await fetch(
          endpoint,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              instruction,
            }),
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Could not start refinement."
        );
      }

      setProject(data);

      const targetLabel =
        isGlobal
          ? "Project refinement"
          : agent?.label ||
            "Agent refinement";

      await waitForProjectCompletion(
        project.project_id,
        (latest) => {
          if (
            latest.status ===
            "completed"
          ) {
            return `${targetLabel} completed.`;
          }

          return getStatusMessage(
            latest
          );
        }
      );

      setRefinementInstruction(
        ""
      );

      setRefinementMode(
        null
      );

      setStatusMessage(
        isGlobal
          ? "Project refinement completed."
          : `${agent?.label || "Artifact"} regenerated.`
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Refinement failed."
      );

      setStatusMessage("");
    } finally {
      setRefining(false);
    }
  }

  async function restoreVersion(
    stage,
    versionNumber
  ) {
    if (
      !project?.project_id ||
      loading ||
      refining
    ) {
      return;
    }

    setRefining(true);
    setError("");

    try {
      const response =
        await fetch(
          `${API_BASE}/projects/${project.project_id}/artifacts/${stage}/versions/${versionNumber}/restore`,
          {
            method: "POST",
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Could not restore version."
        );
      }

      await fetchProject(
        project.project_id
      );

      await fetchArtifacts(
        project.project_id
      );

      await fetchVersions(
        project.project_id
      );

      await fetchEvents(
        project.project_id
      );

      await fetchProjects();

      setActiveArtifact(
        stage ===
          "technical_review"
          ? "review"
          : stage
      );

      setSelectedVersion(
        null
      );

      setSelectedCompareVersion(
        null
      );

      setStatusMessage(
        `Restored ${stage} version ${versionNumber}.`
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Version restore failed."
      );
    } finally {
      setRefining(false);
    }
  }

  async function openProject(
    projectId
  ) {
    if (
      loading ||
      refining
    ) {
      return;
    }

    setError("");
    setWorkspaceReady(false);
    setShowProjects(false);
    setShowVersions(false);
    setShowEvents(false);
    setSelectedVersion(null);
    setSelectedCompareVersion(
      null
    );

    try {
      const loaded =
        await fetchProject(
          projectId
        );

      await fetchArtifacts(
        projectId
      );

      await fetchVersions(
        projectId
      );

      await fetchEvents(
        projectId
      );

      const savedArtifact = safeStorageRead(
        `specra:activeArtifact:${projectId}`
      );
      setIdea(loaded.idea);
      setActiveArtifact(
        VALID_ARTIFACT_KEYS.has(savedArtifact) ? savedArtifact : "requirements"
      );
      setWorkspaceReady(true);
      setShowMemory(false);
      setStatusMessage(getStatusMessage(loaded));
      restoreScrollPosition(projectId);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not open project."
      );
    }
  }

  async function refreshWorkspace() {
    if (
      !project?.project_id
    ) {
      return;
    }

    try {
      await fetchProject(
        project.project_id
      );

      await fetchArtifacts(
        project.project_id
      );

      await fetchVersions(
        project.project_id
      );

      await fetchEvents(
        project.project_id
      );

      await fetchProjects();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Refresh failed."
      );
    }
  }

  async function rerunFullWorkflow() {
    if (!project?.project_id || loading || refining) return;
    setLoading(true);
    setError("");
    setStatusMessage("Starting a fresh workflow with saved project memory...");
    setShowMemory(false);
    try {
      await startFullWorkflow(project.project_id);
      await waitForProjectCompletion(project.project_id);
      await fetchVersions(project.project_id);
      await fetchEvents(project.project_id);
      await fetchProjects();
      setStatusMessage("Project workflow completed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not rerun the project workflow.");
      setStatusMessage("");
    } finally {
      setLoading(false);
    }
  }

  function loadDemoIdea() {
    setIdea(
      DEFAULT_IDEA
    );
    setError("");
  }

  function clearProject() {
    if (
      loading ||
      refining
    ) {
      return;
    }

    setProject(null);
    setWorkspaceReady(false);
    setShowMemory(false);
    safeStorageRemove("specra:lastProjectId");
    setArtifacts(null);
    setIdea("");
    setVersions({});
    setEvents([]);
    setSelectedVersion(null);
    setSelectedCompareVersion(
      null
    );
    setRefinementMode(
      null
    );
    setRefinementInstruction(
      ""
    );
    setError("");
    setStatusMessage("");
  }

  function openAgentRefinement(
    agentKey
  ) {
    setActiveArtifact(
      agentKey
    );

    setRefinementMode(
      agentKey
    );

    setRefinementInstruction(
      ""
    );

    setError("");
    setShowJson(false);
    setShowVersions(false);
  }

  function openGlobalRefinement() {
    setRefinementMode(
      "global"
    );

    setRefinementInstruction(
      ""
    );

    setError("");
  }

  function closeRefinement() {
    setRefinementMode(
      null
    );

    setRefinementInstruction(
      ""
    );
  }

  function openVersionPanel(
    agentKey
  ) {
    setActiveArtifact(
      agentKey
    );

    setShowVersions(
      true
    );

    setSelectedVersion(
      null
    );

    setSelectedCompareVersion(
      null
    );

    setShowEvents(false);
    setRefinementMode(
      null
    );
    setError("");

    if (
      project?.project_id
    ) {
      fetchVersions(
        project.project_id
      );
    }
  }

  function getVersionList() {
    const stage =
      activeArtifact ===
      "review"
        ? "technical_review"
        : activeArtifact;

    return (
      versions?.[stage] ||
      []
    );
  }

  const versionList =
    getVersionList();

  const selectedVersionData =
    versionList.find(
      (item) =>
        item.version_number ===
        selectedVersion
    ) || null;

  const compareVersionData =
    versionList.find(
      (item) =>
        item.version_number ===
        selectedCompareVersion
    ) || null;

  function artifactSummary(
    agent
  ) {
    const data =
      artifacts?.[
        agent.key
      ];

    if (!data) {
      return statusLabel(
        getStageState(
          agent
        )
      );
    }

    if (
      agent.key ===
      "requirements"
    ) {
      const count =
        data.functional_requirements
          ?.length || 0;

      return `${count} functional requirement${
        count === 1
          ? ""
          : "s"
      } identified`;
    }

    if (
      agent.key ===
      "project_plan"
    ) {
      const milestones =
        data.milestones
          ?.length || 0;

      const tasks =
        data.milestones?.reduce(
          (
            total,
            milestone
          ) =>
            total +
            (milestone.tasks
              ?.length || 0),
          0
        ) || 0;

      return `${milestones} milestone${
        milestones === 1
          ? ""
          : "s"
      } • ${tasks} task${
        tasks === 1
          ? ""
          : "s"
      }`;
    }

    if (
      agent.key ===
      "architecture"
    ) {
      const components =
        data.components
          ?.length || 0;

      const endpoints =
        data.api_endpoints
          ?.length || 0;

      return `${components} components • ${endpoints} API endpoints`;
    }

    if (
      agent.key ===
      "review"
    ) {
      return data.overall_status ===
        "PASS"
        ? "Technical review passed"
        : data.overall_status ||
            "Review completed";
    }

    return "Result ready.";
  }

  function renderRequirements(
    data
  ) {
    if (!data) {
      return (
        <div className="empty-artifact">
          Requirements are being generated...
        </div>
      );
    }

    return (
      <div className="artifact-content">
        <div className="result-section">
          <div className="result-label">
            OBJECTIVE
          </div>

          <div className="result-objective">
            {data.objective}
          </div>
        </div>

        <div className="result-section">
          <div className="result-label">
            USER ROLES
          </div>

          <div className="pill-list">
            {data.user_roles?.map(
              (role) => (
                <span
                  className="result-pill"
                  key={role}
                >
                  {role}
                </span>
              )
            )}
          </div>
        </div>

        <div className="result-section">
          <div className="result-label">
            FUNCTIONAL REQUIREMENTS
          </div>

          <div className="requirement-list">
            {data.functional_requirements?.map(
              (
                requirement,
                index
              ) => (
                <div
                  className="requirement-row"
                  key={`${requirement}-${index}`}
                >
                  <span className="requirement-id">
                    FR-
                    {String(
                      index + 1
                    ).padStart(
                      3,
                      "0"
                    )}
                  </span>

                  <span>
                    {requirement}
                  </span>
                </div>
              )
            )}
          </div>
        </div>

        {data.assumptions?.length >
          0 && (
          <div className="result-section">
            <div className="result-label">
              ASSUMPTIONS
            </div>

            <div className="simple-list">
              {data.assumptions.map(
                (item) => (
                  <div
                    className="simple-list-row"
                    key={item}
                  >
                    {item}
                  </div>
                )
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  function renderPlan(
    data
  ) {
    if (!data) {
      return (
        <div className="empty-artifact">
          Project plan is being generated...
        </div>
      );
    }

    return (
      <div className="artifact-content">
        {data.milestones?.map(
          (
            milestone,
            index
          ) => (
            <div
              className="milestone-card"
              key={`${milestone.name}-${index}`}
            >
              <div className="milestone-top">
                <div className="milestone-number">
                  {String(
                    index + 1
                  ).padStart(
                    2,
                    "0"
                  )}
                </div>

                <div>
                  <div className="milestone-name">
                    {milestone.name}
                  </div>

                  <div className="milestone-description">
                    {
                      milestone.description
                    }
                  </div>
                </div>
              </div>

              <div className="requirement-ref-list">
                {milestone.requirement_refs?.map(
                  (ref) => (
                    <span
                      className="ref-badge"
                      key={ref}
                    >
                      {ref}
                    </span>
                  )
                )}
              </div>

              <div className="task-list">
                {milestone.tasks?.map(
                  (
                    task,
                    taskIndex
                  ) => (
                    <div
                      className="task-row"
                      key={`${task.description}-${taskIndex}`}
                    >
                      <span className="task-number">
                        {taskIndex +
                          1}
                      </span>

                      <span>
                        {
                          task.description
                        }
                      </span>

                      <span className="task-refs">
                        {task.requirement_refs?.join(
                          ", "
                        )}
                      </span>
                    </div>
                  )
                )}
              </div>
            </div>
          )
        )}
      </div>
    );
  }

  function renderArchitecture(
    data
  ) {
    if (!data) {
      return (
        <div className="empty-artifact">
          System architecture is being generated...
        </div>
      );
    }

    return (
      <div className="artifact-content">
        <div className="stack-grid">
          <div className="stack-card">
            <span>
              STYLE
            </span>
            <strong>
              {
                data.architecture_style
              }
            </strong>
          </div>

          <div className="stack-card">
            <span>
              FRONTEND
            </span>
            <strong>
              {
                data.frontend
              }
            </strong>
          </div>

          <div className="stack-card">
            <span>
              BACKEND
            </span>
            <strong>
              {data.backend}
            </strong>
          </div>

          <div className="stack-card">
            <span>
              DATABASE
            </span>
            <strong>
              {data.database}
            </strong>
          </div>
        </div>

        <div className="result-section">
          <div className="result-label">
            COMPONENTS
          </div>

          <div className="component-grid">
            {data.components?.map(
              (component) => (
                <div
                  className="component-card"
                  key={
                    component.name
                  }
                >
                  <div className="component-name">
                    {
                      component.name
                    }
                  </div>

                  <div className="component-description">
                    {
                      component.responsibility
                    }
                  </div>

                  <div className="requirement-ref-list">
                    {component.related_requirements?.map(
                      (ref) => (
                        <span
                          className="ref-badge"
                          key={ref}
                        >
                          {ref}
                        </span>
                      )
                    )}
                  </div>
                </div>
              )
            )}
          </div>
        </div>

        <div className="result-section">
          <div className="result-label">
            API ENDPOINTS
          </div>

          <div className="endpoint-list">
            {data.api_endpoints?.map(
              (
                endpoint
              ) => (
                <div
                  className="endpoint-row"
                  key={
                    endpoint.name
                  }
                >
                  <div className="endpoint-name">
                    {
                      endpoint.name
                    }
                  </div>

                  <div className="endpoint-purpose">
                    {
                      endpoint.purpose
                    }
                  </div>

                  <div className="requirement-ref-list">
                    {endpoint.related_requirements?.map(
                      (ref) => (
                        <span
                          className="ref-badge"
                          key={
                            ref
                          }
                        >
                          {ref}
                        </span>
                      )
                    )}
                  </div>
                </div>
              )
            )}
          </div>
        </div>

        <div className="result-section">
          <div className="result-label">
            ARCHITECTURE DECISIONS
          </div>

          <div className="decision-list">
            {data.architecture_decisions?.map(
              (
                decision,
                index
              ) => (
                <div
                  className="decision-card"
                  key={`${decision.decision}-${index}`}
                >
                  <div className="decision-title">
                    {
                      decision.decision
                    }
                  </div>

                  <div className="decision-rationale">
                    {
                      decision.rationale
                    }
                  </div>

                  {decision.related_requirements?.length >
                    0 && (
                    <div className="requirement-ref-list">
                      {decision.related_requirements.map(
                        (
                          ref
                        ) => (
                          <span
                            className="ref-badge"
                            key={
                              ref
                            }
                          >
                            {
                              ref
                            }
                          </span>
                        )
                      )}
                    </div>
                  )}
                </div>
              )
            )}
          </div>
        </div>
      </div>
    );
  }

  function renderReview(
    data
  ) {
    if (!data) {
      return (
        <div className="empty-artifact">
          Technical review is being generated...
        </div>
      );
    }

    const passed =
      data.overall_status ===
      "PASS";

    return (
      <div className="artifact-content">
        <div
          className={
            passed
              ? "review-banner pass"
              : "review-banner revise"
          }
        >
          <div>
            <div className="review-status-label">
              TECHNICAL REVIEW
            </div>

            <div className="review-status-value">
              {
                data.overall_status
              }
            </div>
          </div>

          <div className="review-summary">
            {data.summary}
          </div>
        </div>

        <div className="result-section">
          <div className="result-label">
            REQUIREMENT COVERAGE
          </div>

          <div className="coverage-list">
            {data.requirement_coverage?.map(
              (
                coverage
              ) => (
                <div
                  className="coverage-row"
                  key={
                    coverage.requirement_id
                  }
                >
                  <span className="coverage-id">
                    {
                      coverage.requirement_id
                    }
                  </span>

                  <span className="coverage-text">
                    {
                      coverage.requirement
                    }
                  </span>

                  <span className="coverage-check">
                    {coverage.in_project_plan &&
                    coverage.in_architecture &&
                    coverage.in_api
                      ? "✓ Complete"
                      : "Needs attention"}
                  </span>
                </div>
              )
            )}
          </div>
        </div>

        {data.findings?.length >
          0 && (
          <div className="result-section">
            <div className="result-label">
              FINDINGS
            </div>

            <div className="finding-list">
              {data.findings.map(
                (
                  finding,
                  index
                ) => (
                  <div
                    className="finding-card"
                    key={`${finding.title}-${index}`}
                  >
                    <div className="finding-head">
                      <span className="finding-severity">
                        {
                          finding.severity
                        }
                      </span>

                      <span className="finding-title">
                        {
                          finding.title
                        }
                      </span>
                    </div>

                    <div className="finding-evidence">
                      {
                        finding.evidence
                      }
                    </div>

                    <div className="finding-recommendation">
                      {
                        finding.recommendation
                      }
                    </div>
                  </div>
                )
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  function renderArtifact() {
    if (showJson) {
      return (
        <div className="json-viewer">
          <pre>
            {JSON.stringify(
              activeData,
              null,
              2
            )}
          </pre>
        </div>
      );
    }

    if (
      activeArtifact ===
      "requirements"
    ) {
      return renderRequirements(
        activeData
      );
    }

    if (
      activeArtifact ===
      "project_plan"
    ) {
      return renderPlan(
        activeData
      );
    }

    if (
      activeArtifact ===
      "architecture"
    ) {
      return renderArchitecture(
        activeData
      );
    }

    return renderReview(
      activeData
    );
  }

  function renderVersionHistory() {
    const stage =
      activeArtifact ===
      "review"
        ? "technical_review"
        : activeArtifact;

    const stageVersions =
      versions?.[stage] ||
      [];

    const diffRows =
      selectedVersionData &&
      compareVersionData
        ? buildHumanDiff(
            compareVersionData.content,
            selectedVersionData.content
          )
        : [];

    const addedCount =
      diffRows.filter(
        (row) =>
          row.kind === "added"
      ).length;

    const removedCount =
      diffRows.filter(
        (row) =>
          row.kind === "removed"
      ).length;

    const changedCount =
      diffRows.filter(
        (row) =>
          row.kind === "changed"
      ).length;

    if (
      stageVersions.length ===
      0
    ) {
      return (
        <div className="version-panel">
          <div className="version-panel-header">
            <div>
              <div className="result-label">
                VERSION HISTORY
              </div>

              <div className="version-panel-title">
                {
                  AGENT_CONFIG.find(
                    (agent) =>
                      agent.key ===
                      activeArtifact
                  )?.label
                }
              </div>
            </div>

            <button
              className="secondary-button"
              onClick={() =>
                setShowVersions(
                  false
                )
              }
            >
              Close
            </button>
          </div>

          <div className="empty-history">
            No saved versions for this artifact yet.
          </div>
        </div>
      );
    }

    return (
      <div className="version-panel">
        <div className="version-panel-header">
          <div>
            <div className="result-label">
              VERSION HISTORY
            </div>

            <div className="version-panel-title">
              {
                AGENT_CONFIG.find(
                  (agent) =>
                    agent.key ===
                    activeArtifact
                )?.label
              }
            </div>

            <div className="version-panel-subtitle">
              Every refinement creates a new version.
            </div>
          </div>

          <button
            className="secondary-button"
            onClick={() =>
              setShowVersions(
                false
              )
            }
          >
            Close
          </button>
        </div>

        <div className="version-list">
          {stageVersions.map(
            (version) => (
              <div
                className={
                  selectedVersion ===
                  version.version_number
                    ? "version-row selected"
                    : "version-row"
                }
                key={
                  version.version_number
                }
              >
                <button
                  className="version-select"
                  onClick={() =>
                    selectVersionForComparison(
                      version.version_number
                    )
                  }
                >
                  <span className="version-number">
                    v
                    {
                      version.version_number
                    }
                  </span>

                  <span className="version-info">
                    <strong>
                      {version.source}
                    </strong>

                    <small>
                      {
                        version.created_at
                      }
                    </small>

                    {version.instruction && (
                      <small>
                        {
                          version.instruction
                        }
                      </small>
                    )}
                  </span>
                </button>

                <button
                  className="version-restore"
                  disabled={
                    refining ||
                    loading
                  }
                  onClick={() =>
                    restoreVersion(
                      stage,
                      version.version_number
                    )
                  }
                >
                  Restore
                </button>
              </div>
            )
          )}
        </div>

        {selectedVersionData && (
          <div className="version-preview">
            <div className="preview-header">
              <div>
                <div className="result-label">
                  SELECTED VERSION
                </div>

                <div className="preview-version">
                  v
                  {
                    selectedVersionData.version_number
                  }
                </div>
              </div>
            </div>

            <div className="version-meta-grid">
              <div className="version-meta-item">
                <span>SOURCE</span>

                <strong>
                  {
                    selectedVersionData.source
                  }
                </strong>
              </div>

              <div className="version-meta-item">
                <span>CREATED</span>

                <strong>
                  {
                    selectedVersionData.created_at
                  }
                </strong>
              </div>

              <div className="version-meta-item wide">
                <span>INSTRUCTION</span>

                <strong>
                  {
                    selectedVersionData.instruction ||
                    "Initial artifact generation"
                  }
                </strong>
              </div>
            </div>
          </div>
        )}

        {selectedVersionData &&
          versionList.length > 1 && (
            <div className="compare-box">
              <div className="result-label">
                COMPARE CHANGES
              </div>

              <div className="compare-selector">
                {stageVersions
                  .filter(
                    (version) =>
                      version.version_number !==
                      selectedVersionData.version_number
                  )
                  .map(
                    (version) => (
                      <button
                        key={
                          version.version_number
                        }
                        className={
                          selectedCompareVersion ===
                          version.version_number
                            ? "compare-version active"
                            : "compare-version"
                        }
                        onClick={() =>
                          setSelectedCompareVersion(
                            version.version_number
                          )
                        }
                      >
                        Compare with v
                        {
                          version.version_number
                        }
                      </button>
                    )
                  )}
              </div>

              {compareVersionData && (
                <>
                  <div className="diff-summary">
                    <div className="diff-summary-item">
                      <strong>
                        {addedCount}
                      </strong>
                      <span>Added</span>
                    </div>

                    <div className="diff-summary-item">
                      <strong>
                        {changedCount}
                      </strong>
                      <span>Changed</span>
                    </div>

                    <div className="diff-summary-item">
                      <strong>
                        {removedCount}
                      </strong>
                      <span>Removed</span>
                    </div>

                    <div className="diff-summary-context">
                      v
                      {
                        compareVersionData.version_number
                      }
                      <span>→</span>
                      v
                      {
                        selectedVersionData.version_number
                      }
                    </div>
                  </div>

                  {diffRows.length ===
                  0 ? (
                    <div className="diff-empty">
                      No changes between these versions.
                    </div>
                  ) : (
                    <div className="diff-list">
                      {diffRows.map(
                        (
                          row,
                          index
                        ) => (
                          <div
                            className={`diff-row ${row.kind}`}
                            key={`${row.path}-${index}`}
                          >
                            <div className="diff-row-head">
                              <span className="diff-kind">
                                {row.kind ===
                                "added"
                                  ? "+"
                                  : row.kind ===
                                    "removed"
                                  ? "−"
                                  : "~"}
                              </span>

                              <span className="diff-path">
                                {
                                  row.path
                                }
                              </span>
                            </div>

                            {row.kind !==
                              "added" && (
                              <div className="diff-value before">
                                <span>
                                  Before
                                </span>
                                <code>
                                  {
                                    formatDiffValue(
                                      row.before
                                    )
                                  }
                                </code>
                              </div>
                            )}

                            {row.kind !==
                              "removed" && (
                              <div className="diff-value after">
                                <span>
                                  After
                                </span>
                                <code>
                                  {
                                    formatDiffValue(
                                      row.after
                                    )
                                  }
                                </code>
                              </div>
                            )}
                          </div>
                        )
                      )}
                    </div>
                  )}

                  <div className="raw-compare">
                    <details>
                      <summary>
                        View raw JSON comparison
                      </summary>

                      <div className="compare-grid">
                        <div>
                          <div className="compare-title">
                            v
                            {
                              compareVersionData.version_number
                            }
                          </div>

                          <pre>
                            {JSON.stringify(
                              compareVersionData.content,
                              null,
                              2
                            )}
                          </pre>
                        </div>

                        <div>
                          <div className="compare-title">
                            v
                            {
                              selectedVersionData.version_number
                            }
                          </div>

                          <pre>
                            {JSON.stringify(
                              selectedVersionData.content,
                              null,
                              2
                            )}
                          </pre>
                        </div>
                      </div>
                    </details>
                  </div>
                </>
              )}
            </div>
          )}
      </div>
    );
  }

  function renderEventPanel() {
    if (
      events.length ===
      0
    ) {
      return (
        <div className="empty-history">
          No project activity yet.
        </div>
      );
    }

    return (
      <div className="event-panel">
        <div className="version-panel-header">
          <div>
            <div className="result-label">
              ACTIVITY
            </div>

            <div className="version-panel-title">
              Project event history
            </div>
          </div>

          <button
            className="secondary-button"
            onClick={() =>
              setShowEvents(
                false
              )
            }
          >
            Close
          </button>
        </div>

        <div className="event-list">
          {events.map(
            (event) => (
              <div
                className="event-row"
                key={
                  event.event_id
                }
              >
                <div className="event-marker">
                  •
                </div>

                <div className="event-content">
                  <div className="event-top">
                    <span>
                      {
                        event.event_type
                      }
                    </span>

                    <small>
                      {
                        event.created_at
                      }
                    </small>
                  </div>

                  <div className="event-message">
                    {
                      event.message
                    }
                  </div>

                  {event.stage && (
                    <div className="event-stage">
                      {
                        STAGE_LABELS[
                          event.stage
                        ] ||
                        event.stage
                      }
                    </div>
                  )}
                </div>
              </div>
            )
          )}
        </div>
      </div>
    );
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrapWorkspace() {
      const savedProjectId = safeStorageRead("specra:lastProjectId");
      try {
        const availableProjects = await fetchProjects();
        if (cancelled) return;
        const exists = savedProjectId && availableProjects.some(
          (item) => item.project_id === savedProjectId
        );
        if (!exists) {
          if (savedProjectId) safeStorageRemove("specra:lastProjectId");
          setWorkspaceReady(false);
          return;
        }

        const savedArtifact = safeStorageRead(
          `specra:activeArtifact:${savedProjectId}`
        );
        try {
          const loaded = await fetchProject(savedProjectId);
          await fetchArtifacts(savedProjectId);
          await fetchVersions(savedProjectId);
          await fetchEvents(savedProjectId);
          if (cancelled) return;
          setIdea(loaded.idea);
          setActiveArtifact(
            VALID_ARTIFACT_KEYS.has(savedArtifact) ? savedArtifact : "requirements"
          );
          setStatusMessage(getStatusMessage(loaded));
          setWorkspaceReady(true);
          restoreScrollPosition(savedProjectId);
        } catch {
          safeStorageRemove("specra:lastProjectId");
          setProject(null);
          setArtifacts(null);
          setWorkspaceReady(false);
          setError("The last project is no longer available from the backend. It may have been lost during a server restart or redeploy.");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load projects.");
        }
      }
    }

    bootstrapWorkspace();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!workspaceReady || !project?.project_id) return;
    safeStorageWrite(`specra:activeArtifact:${project.project_id}`, activeArtifact);
  }, [workspaceReady, project?.project_id, activeArtifact]);

  useEffect(() => {
    if (!workspaceReady || !project?.project_id) return;
    const projectId = project.project_id;
    const key = `specra:scroll:${projectId}`;
    let pendingFrame = null;
    const saveScroll = () => {
      pendingFrame = null;
      safeStorageWrite(key, String(window.scrollY));
    };
    const onScroll = () => {
      if (pendingFrame === null) pendingFrame = window.requestAnimationFrame(saveScroll);
    };
    const saveOnPageHide = () => {
      safeStorageWrite(key, String(window.scrollY));
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("pagehide", saveOnPageHide);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("pagehide", saveOnPageHide);
      if (pendingFrame !== null) window.cancelAnimationFrame(pendingFrame);
      safeStorageWrite(key, String(window.scrollY));
    };
  }, [workspaceReady, project?.project_id]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            S
          </div>

          <div>
            <div className="brand-name">
              Specra
            </div>

            <div className="brand-subtitle">
              Multi-Agent Software Engineering
            </div>
          </div>
        </div>

        <div className="topbar-meta">
          <div className="status-dot">
            <span />
            AI Provider
          </div>

          <button
            className="ghost-button"
            onClick={() =>
              setShowProjects(
                !showProjects
              )
            }
          >
            Projects
          </button>

          {project && currentUser && (
            <>
              <button
                className="ghost-button"
                onClick={() => {
                  setShowTesting(false);
                  setShowTeam((value) => !value);
                }}
              >
                {showTeam ? "Close Team" : "Team"}
              </button>
              <button
                className="ghost-button"
                onClick={() => {
                  setShowTeam(false);
                  setShowCopilot(false);
                  setShowCodeStudio(false);
                  setShowTesting((value) => !value);
                }}
              >
                {showTesting ? "Close Testing" : "Testing & Docs"}
              </button>
              <button
                className="ghost-button"
                onClick={() => {
                  setShowTeam(false);
                  setShowTesting(false);
                  setShowCodeStudio(false);
                  setShowCopilot((value) => !value);
                }}
              >
                {showCopilot ? "Close Copilot" : "AI Copilot"}
              </button>
              <button
                className="ghost-button"
                onClick={() => {
                  setShowTeam(false);
                  setShowTesting(false);
                  setShowCopilot(false);
                  setShowCodeStudio((value) => !value);
                }}
              >
                {showCodeStudio ? "Close Code Studio" : "Code Studio"}
              </button>
            </>
          )}

          {project &&
            currentUser &&
            ["admin", "analyst"].includes(currentUser.role) && (
              <button
                className="ghost-button"
                onClick={clearProject}
                disabled={loading || refining}
              >
                New Project
              </button>
            )}
        </div>
      </header>

      {showTeam && project && (
        <ProjectTeamPanel
          projectId={project.project_id}
          onClose={() => setShowTeam(false)}
        />
      )}

      {showTesting && project && (
        <ProjectTestingPanel
          projectId={project.project_id}
          onClose={() => setShowTesting(false)}
        />
      )}

      {showCopilot && project && (
        <ProjectCopilotPanel
          projectId={project.project_id}
          onClose={() => setShowCopilot(false)}
          onUseSuggestion={(proposal) => {
            const target = proposal.target_artifact;
            setActiveArtifact(target);
            setRefinementMode(target);
            setRefinementInstruction(proposal.suggested_instruction);
            setShowCopilot(false);
            setError("");
            setStatusMessage("Copilot suggestion loaded for review. No artifact has changed yet.");
          }}
        />
      )}

      {showCodeStudio && project && (
        <CodeStudioPanel
          projectId={project.project_id}
          onClose={() => setShowCodeStudio(false)}
        />
      )}

      {showProjects && (
        <div className="projects-popover">
          <div className="projects-popover-header">
            <div>
              <div className="result-label">
                PROJECTS
              </div>

              <div className="projects-popover-title">
                Your engineering work
              </div>
            </div>

            <button
              className="secondary-button"
              onClick={() =>
                setShowProjects(
                  false
                )
              }
            >
              Close
            </button>
          </div>

          <div className="project-list">
            {projects.length ===
            0 ? (
              <div className="empty-history">
                No saved projects yet.
              </div>
            ) : (
              projects.map(
                (item) => (
                  <button
                    className={
                      project?.project_id ===
                      item.project_id
                        ? "saved-project active"
                        : "saved-project"
                    }
                    key={
                      item.project_id
                    }
                    onClick={() =>
                      openProject(
                        item.project_id
                      )
                    }
                  >
                    <div className="saved-project-top">
                      <span>
                        {
                          item.project_name ||
                          "Untitled Project"
                        }
                      </span>

                      <span>
                        {
                          item.status
                        }
                      </span>
                    </div>

                    <div className="saved-project-idea">
                      {
                        item.idea
                      }
                    </div>

                    <div className="saved-project-meta">
                      {
                        item.updated_at
                      }
                    </div>
                  </button>
                )
              )
            )}
          </div>
        </div>
      )}

      <main className="main-content">
        <section className="hero-section">
          <div className="eyebrow">
            AI-POWERED SOFTWARE ENGINEERING
          </div>

          <h1>
            Turn an idea into a
            <span>
              technical blueprint.
            </span>
          </h1>

          <p className="hero-copy">
            Describe what you want to build.
            Our AI engineering pipeline transforms
            it into requirements, a project plan,
            system architecture, and a technical
            review.
          </p>

          {!project &&
            currentUser &&
            ["admin", "analyst"].includes(currentUser.role) && (
            <div className="idea-card">
              <div className="input-header">
                <div>
                  <div className="input-label">
                    What do you want to build?
                  </div>

                  <div className="input-hint">
                    Describe the product, platform,
                    application, or system in natural
                    language.
                  </div>
                </div>

                <button
                  className="demo-button"
                  onClick={
                    loadDemoIdea
                  }
                >
                  Load demo idea
                </button>
              </div>

              <textarea
                value={idea}
                onChange={(event) =>
                  setIdea(
                    event.target.value
                  )
                }
                placeholder="Example: Build a college learning management system..."
                disabled={
                  loading ||
                  refining
                }
              />

              <div className="input-footer">
                <div className="input-counter">
                  {idea.length} characters
                </div>

                <button
                  className="primary-button"
                  onClick={
                    handleBuild
                  }
                  disabled={
                    loading ||
                    refining ||
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

          {!project &&
            currentUser &&
            !["admin", "analyst"].includes(currentUser.role) && (
              <div className="idea-card role-workspace-notice">
                <div className="input-label">No project assigned yet</div>
                <p className="hero-copy">
                  Your account's default role is {currentUser.role}. Ask the workspace
                  administrator to add you to an existing project with your job-area
                  permissions, or assign you the analyst role if you need to create
                  new projects.
                </p>
              </div>
            )}

          {project && (
            <div className="workflow-card">
              <div className="workflow-card-top">
                <div>
                  <div className="workflow-eyebrow">
                    PROJECT WORKSPACE
                  </div>

                  <h2>
                    {
                      project.project_name ||
                      artifacts?.project_name ||
                      "Project"
                    }
                  </h2>

                  <div className="workflow-id">
                    {
                      project.project_id
                    }
                  </div>
                </div>

                <div
                  className={
                    project.status ===
                    "completed"
                      ? project.approved
                        ? "approved-badge"
                        : "running-badge"
                      : "running-badge"
                  }
                >
                  {project.status ===
                  "completed"
                    ? project.approved
                      ? "✓ Approved"
                      : "Needs Revision"
                    : project.status ===
                        "interrupted"
                      ? "Interrupted"
                      : "● Running"}
                </div>
              </div>

              <div className="idea-summary">
                <div className="result-label">
                  PROJECT IDEA
                </div>

                <div>
                  {
                    project.idea
                  }
                </div>
              </div>

              <div className="live-stage-list">
                {AGENT_CONFIG.map(
                  (agent) => {
                    const state =
                      getStageState(
                        agent
                      );

                    return (
                      <button
                        className={`live-stage ${state}`}
                        key={
                          agent.key
                        }
                        onClick={() =>
                          setActiveArtifact(
                            agent.key
                          )
                        }
                      >
                        <div className="live-stage-icon">
                          {state ===
                          "completed"
                            ? "✓"
                            : state ===
                                "running"
                              ? "•"
                              : state ===
                                  "failed"
                                ? "!"
                                : state ===
                                    "interrupted"
                                  ? "!"
                                  : agent.icon}
                        </div>

                        <div>
                          <div className="live-stage-name">
                            {
                              agent.label
                            }
                          </div>

                          <div className="live-stage-status">
                            {statusLabel(
                              state
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  }
                )}
              </div>

              {(loading ||
                refining) && (
                <div className="run-message">
                  <span className="pulse-orb" />

                  <span>
                    {
                      statusMessage
                    }
                  </span>
                </div>
              )}

              {error && (
                <div className="error-box">
                  <div className="error-title">
                    Operation error
                  </div>

                  <div className="error-message">
                    {error}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {project && (
          <section className="workspace">
            <div className="workspace-header">
              <div>
                <div className="workspace-eyebrow">
                  ENGINEERING ARTIFACTS
                </div>

                <h2>
                  Work produced by the AI team
                </h2>

                <div className="workspace-meta">
                  <span>
                    Every artifact is persisted and
                    versioned.
                  </span>

                  {project.artifact_versions && (
                    <span className="workspace-version-summary">
                      {
                        Object.values(
                          project.artifact_versions
                        ).filter(
                          (version) =>
                            version > 0
                        ).length
                      } stages versioned
                    </span>
                  )}

                  {getStaleAgents().length > 0 && (
                    <span className="workspace-stale-summary">
                      {
                        getStaleAgents().length
                      } stale
                    </span>
                  )}
                </div>
              </div>

              <div className="workspace-actions">
                <button
                  className="secondary-button"
                  onClick={
                    refreshWorkspace
                  }
                  disabled={
                    loading ||
                    refining
                  }
                >
                  Refresh
                </button>

                <button
                  className="secondary-button"
                  onClick={() => setShowMemory((current) => !current)}
                  disabled={loading || refining}
                >
                  Project Memory
                </button>

                <button
                  className="secondary-button"
                  onClick={rerunFullWorkflow}
                  disabled={loading || refining}
                  title="Run all four agents again using saved project memory"
                >
                  {loading ? "Running..." : "Run All Again"}
                </button>

                <button
                  className="secondary-button"
                  onClick={() => {
                    setShowEvents(
                      !showEvents
                    );
                    setShowVersions(
                      false
                    );
                    if (
                      project?.project_id
                    ) {
                      fetchEvents(
                        project.project_id
                      );
                    }
                  }}
                >
                  Activity
                </button>

                <button
                  className="refine-global-button"
                  onClick={
                    openGlobalRefinement
                  }
                  disabled={
                    loading ||
                    refining ||
                    project.status !==
                      "completed"
                  }
                >
                  Refine Entire Project
                </button>
              </div>
            </div>

            {showMemory && project?.project_id && (
              <ProjectMemoryPanel
                apiBase={API_BASE}
                projectId={project.project_id}
                onClose={() => setShowMemory(false)}
              />
            )}

            {getStaleAgents().length >
              0 && (
              <div className="stale-banner">
                <div className="stale-banner-copy">
                  <div className="stale-banner-title">
                    {getStaleAgents().length} artifact
                    {getStaleAgents().length ===
                    1
                      ? ""
                      : "s"} need rebuilding
                  </div>

                  <div className="stale-banner-text">
                    An upstream artifact changed. Downstream
                    results are kept for history but should not
                    be treated as current until rebuilt.
                  </div>
                </div>

                <button
                  className="stale-rebuild-button"
                  onClick={() =>
                    rebuildFromStage(
                      getStaleAgents()[0]
                        .key
                    )
                  }
                  disabled={
                    loading ||
                    refining
                  }
                >
                  Rebuild affected stages →
                </button>
              </div>
            )}

            {refinementMode ===
              "global" && (
              <div className="global-refinement">
                <div>
                  <div className="refinement-kicker">
                    GLOBAL PROJECT INSTRUCTION
                  </div>

                  <div className="refinement-title">
                    Tell the entire AI team what
                    should change.
                  </div>
                </div>

                <textarea
                  value={
                    refinementInstruction
                  }
                  onChange={(event) =>
                    setRefinementInstruction(
                      event.target.value
                    )
                  }
                  placeholder="Example: Add restaurant-owner functionality and make the payment flow support cash on delivery..."
                  disabled={
                    refining
                  }
                />

                <div className="refinement-actions">
                  <button
                    className="secondary-button"
                    onClick={
                      closeRefinement
                    }
                  >
                    Cancel
                  </button>

                  <button
                    className="primary-button"
                    onClick={
                      submitRefinement
                    }
                    disabled={
                      refining ||
                      !refinementInstruction.trim()
                    }
                  >
                    {refining
                      ? "Regenerating..."
                      : "Apply to Project →"}
                  </button>
                </div>
              </div>
            )}

            {showEvents &&
              renderEventPanel()}

            <div className="agent-grid">
              {AGENT_CONFIG.map(
                (agent) => {
                  const state =
                    getStageState(
                      agent
                    );

                  const hasArtifact =
                    Boolean(
                      artifacts?.[
                        agent.key
                      ]
                    );

                  return (
                    <button
                      key={
                        agent.key
                      }
                      className={
                        activeArtifact ===
                        agent.key
                          ? "agent-card active"
                          : "agent-card"
                      }
                      onClick={() =>
                        setActiveArtifact(
                          agent.key
                        )
                      }
                    >
                      <div
                        className={
                          state ===
                          "completed"
                            ? "agent-number completed"
                            : "agent-number"
                        }
                      >
                        {
                          agent.icon
                        }
                      </div>

                      <div className="agent-info">
                        <div className="agent-label">
                          {
                            agent.label
                          }
                        </div>

                        <div className="agent-subtitle">
                          {
                            agent.subtitle
                          }
                        </div>

                        <div
                          className={
                            state === "stale"
                              ? "agent-summary stale-summary"
                              : "agent-summary"
                          }
                        >
                          {state === "stale"
                            ? "Needs rebuild"
                            : hasArtifact
                              ? artifactSummary(
                                  agent
                                )
                              : statusLabel(
                                  state
                                )}
                        </div>
                      </div>

                      <div
                        className={
                          state ===
                          "completed"
                            ? "agent-check"
                            : "agent-state-dot"
                        }
                      >
                        {state ===
                        "completed"
                          ? "✓"
                          : state ===
                              "running"
                            ? "•"
                            : ""}
                      </div>
                    </button>
                  );
                }
              )}
            </div>

            <div className="artifact-layout">
              <aside className="artifact-sidebar">
                <div className="sidebar-title">
                  Artifacts
                </div>

                {AGENT_CONFIG.map(
                  (agent) => {
                    const state =
                      getStageState(
                        agent
                      );

                    return (
                      <button
                        key={
                          agent.key
                        }
                        className={
                          activeArtifact ===
                          agent.key
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
                          <span>
                            {
                              agent.label
                            }
                          </span>

                          <small
                            className={
                              state ===
                              "completed"
                                ? "nav-complete"
                                : ""
                            }
                          >
                            {
                              statusLabel(
                                state
                              )
                            }
                          </small>
                        </span>

                        <span className="nav-arrow">
                          →
                        </span>
                      </button>
                    );
                  }
                )}

                <div className="sidebar-divider" />

                <button
                  className={
                    showVersions
                      ? "sidebar-tool active"
                      : "sidebar-tool"
                  }
                  onClick={() =>
                    openVersionPanel(
                      activeArtifact
                    )
                  }
                >
                  Version History
                </button>

                <div className="sidebar-note">
                  <div className="sidebar-note-title">
                    Traceability
                  </div>

                  <div className="sidebar-note-copy">
                    Requirement IDs flow from
                    requirements into planning,
                    architecture, APIs, and review.
                  </div>
                </div>
              </aside>

              <section className="artifact-panel">
                <div className="artifact-header">
                  <div>
                    <div className="artifact-kicker">
                      {
                        AGENT_CONFIG.find(
                          (agent) =>
                            agent.key ===
                            activeArtifact
                        )?.subtitle
                      }
                    </div>

                    <h3>
                      {
                        AGENT_CONFIG.find(
                          (agent) =>
                            agent.key ===
                            activeArtifact
                        )?.label
                      }
                    </h3>

                    <div className="artifact-result-caption">
                      {activeData
                        ? (() => {
                            const version =
                              getArtifactVersion(
                                activeArtifact
                              );

                            const state =
                              getStageState(
                                AGENT_CONFIG.find(
                                  (agent) =>
                                    agent.key ===
                                    activeArtifact
                                )
                              );

                            if (
                              state ===
                              "stale"
                            ) {
                              return `v${version} • stale • rebuild required`;
                            }

                            return `v${version} • current result`;
                          })()
                        : "Result will appear here"}
                    </div>
                  </div>

                  <div className="artifact-header-actions">
                    {activeData && (
                      <button
                        className="secondary-button"
                        onClick={() =>
                          setShowJson(
                            !showJson
                          )
                        }
                      >
                        {showJson
                          ? "Visual View"
                          : "View JSON"}
                      </button>
                    )}

                    <button
                      className="secondary-button"
                      onClick={() =>
                        openAgentRefinement(
                          activeArtifact
                        )
                      }
                      disabled={
                        loading ||
                        refining ||
                        project.status !==
                          "completed" ||
                        !activeData
                      }
                    >
                      Ask this agent
                    </button>

                    <div className="artifact-status">
                      {
                        statusLabel(
                          getStageState(
                            AGENT_CONFIG.find(
                              (
                                agent
                              ) =>
                                agent.key ===
                                activeArtifact
                            )
                          )
                        )
                      }
                    </div>
                  </div>
                </div>

                {renderArtifact()}


                <QualityLabPanel projectId={project.project_id} />
                {showVersions &&
                  renderVersionHistory()}

                {!showVersions &&
                  refinementMode ===
                    activeArtifact && (
                    <div className="agent-refinement-box">
                      <div className="refinement-kicker">
                        AI REFINEMENT
                      </div>

                      <div className="refinement-title">
                        {
                          AGENT_CONFIG.find(
                            (agent) =>
                              agent.key ===
                              activeArtifact
                          )?.actionLabel
                        }
                      </div>

                      <div className="refinement-description">
                        Tell this agent what to
                        change. A change here updates
                        downstream artifacts automatically.
                      </div>

                      <textarea
                        value={
                          refinementInstruction
                        }
                        onChange={(
                          event
                        ) =>
                          setRefinementInstruction(
                            event.target.value
                          )
                        }
                        placeholder="Example: Add a requirement for order cancellation before preparation..."
                        disabled={
                          refining
                        }
                      />

                      <div className="refinement-actions">
                        <button
                          className="secondary-button"
                          onClick={
                            closeRefinement
                          }
                          disabled={
                            refining
                          }
                        >
                          Cancel
                        </button>

                        <button
                          className="primary-button"
                          onClick={
                            submitRefinement
                          }
                          disabled={
                            refining ||
                            !refinementInstruction.trim()
                          }
                        >
                          {refining
                            ? "Regenerating..."
                            : `Regenerate ${
                                AGENT_CONFIG.find(
                                  (
                                    agent
                                  ) =>
                                    agent.key ===
                                    activeArtifact
                                )?.label
                              } →`}
                        </button>
                      </div>
                    </div>
                  )}

                {!showVersions &&
                  !refinementMode &&
                  activeData && (
                    <div className="quick-edit-bar">
                      <div>
                        <div className="quick-edit-title">
                          Want to change this result?
                        </div>

                        <div className="quick-edit-copy">
                          Ask the current agent, inspect
                          earlier versions, or restore a
                          previous result.
                        </div>
                      </div>

                      <div className="quick-edit-actions">
                        {getStageState(
                          AGENT_CONFIG.find(
                            (agent) =>
                              agent.key ===
                              activeArtifact
                          )
                        ) ===
                          "stale" && (
                          <button
                            className="stale-rebuild-button"
                            onClick={() =>
                              rebuildFromStage(
                                activeArtifact
                              )
                            }
                            disabled={
                              refining ||
                              loading
                            }
                          >
                            Rebuild
                          </button>
                        )}

                        <button
                          className="secondary-button"
                          onClick={() =>
                            openAgentRefinement(
                              activeArtifact
                            )
                          }
                          disabled={
                            refining ||
                            loading ||
                            project.status !==
                              "completed"
                          }
                        >
                          Ask this agent
                        </button>

                        <button
                          className="secondary-button"
                          onClick={() =>
                            openVersionPanel(
                              activeArtifact
                            )
                          }
                        >
                          Versions
                        </button>
                      </div>
                    </div>
                  )}
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
            {AGENT_CONFIG.map(
              (
                agent,
                index
              ) => (
                <div
                  className="pipeline-item"
                  key={
                    agent.key
                  }
                >
                  <div className="pipeline-step">
                    <span>
                      {
                        agent.icon
                      }
                    </span>
                  </div>

                  <div className="pipeline-copy">
                    <div className="pipeline-title">
                      {
                        agent.label
                      }
                    </div>

                    <div className="pipeline-description">
                      {index ===
                        0 &&
                        "Extract the software requirements."}

                      {index ===
                        1 &&
                        "Organize the work into milestones and tasks."}

                      {index ===
                        2 &&
                        "Transform requirements into system architecture."}

                      {index ===
                        3 &&
                        "Audit coverage, traceability, and consistency."}
                    </div>
                  </div>

                  {index <
                    AGENT_CONFIG.length -
                      1 && (
                    <div className="pipeline-line" />
                  )}
                </div>
              )
            )}
          </div>
        </section>
      </main>

      <footer className="footer">
        <div>
          Specra
        </div>

        <div>
          AI Engineering • FastAPI • React
        </div>
      </footer>
    </div>
  );
}

export default App;