import { useCallback, useEffect, useState } from "react";

const TEAM_ROLES = ["analyst", "planner", "architect", "tester", "reviewer", "developer", "viewer"];

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Request failed (${response.status}).`);
  }
  return data;
}

export default function ProjectTeamPanel({ projectId, onClose }) {
  const [members, setMembers] = useState([]);
  const [myRole, setMyRole] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const loadMembers = useCallback(async () => {
    try {
      const data = await request(`/api/v1/projects/${projectId}/members`);
      setMembers(data.members || []);
      setMyRole(data.my_role || "");
    } catch (err) {
      setError(err.message || "Unable to load project members.");
    }
  }, [projectId]);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  const canManage = myRole === "owner" || myRole === "admin";

  async function addMember(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await request(`/api/v1/projects/${projectId}/members`, {
        method: "POST",
        body: JSON.stringify({ email, role }),
      });
      setEmail("");
      setMessage("Team member added.");
      await loadMembers();
    } catch (err) {
      setError(err.message || "Unable to add team member.");
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(userId) {
    setError("");
    setMessage("");
    try {
      await request(`/api/v1/projects/${projectId}/members/${userId}`, {
        method: "DELETE",
      });
      setMessage("Team member removed.");
      await loadMembers();
    } catch (err) {
      setError(err.message || "Unable to remove team member.");
    }
  }

  return (
    <section className="team-panel">
      <div className="team-panel-header">
        <div>
          <div className="auth-eyebrow">PROJECT ACCESS</div>
          <h2>Project team</h2>
          <p>Assign each person the job area they are responsible for.</p>
        </div>
        <button className="auth-secondary-button" onClick={onClose}>Close</button>
      </div>

      <div className="team-role-banner">
        Your role for this project: <strong>{myRole || "checking…"}</strong>
      </div>

      {canManage && (
        <form className="team-add-form" onSubmit={addMember}>
          <label>
            Existing Specra account email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="teammate@example.com"
              required
            />
          </label>
          <label>
            Project role
            <select value={role} onChange={(event) => setRole(event.target.value)}>
              {TEAM_ROLES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <button className="auth-primary-button" disabled={busy}>
            {busy ? "Saving…" : "Add member"}
          </button>
        </form>
      )}

      {error && <p className="auth-error" role="alert">{error}</p>}
      {message && <p className="auth-success" role="status">{message}</p>}

      {members.length === 0 ? (
        <p className="team-empty">No additional members have been assigned to this project.</p>
      ) : (
        <div className="team-member-list">
          {members.map((member) => (
            <div className="team-member" key={member.user_id}>
              <div className="team-member-avatar">{(member.display_name || "U").slice(0, 1).toUpperCase()}</div>
              <div className="team-member-detail">
                <strong>{member.display_name}</strong>
                <span>{member.email}</span>
              </div>
              <span className="auth-role-chip">{member.role}</span>
              {canManage && member.role !== "owner" && (
                <button className="auth-secondary-button" onClick={() => removeMember(member.user_id)}>
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!canManage && (
        <p className="team-help">Only the project owner or an administrator can change team access.</p>
      )}
    </section>
  );
}
