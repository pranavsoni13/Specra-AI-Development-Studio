import { useCallback, useEffect, useState } from "react";

const ROLE_OPTIONS = [
  "admin",
  "analyst",
  "planner",
  "architect",
  "tester",
  "reviewer",
  "developer",
  "viewer",
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

function AdminAccountsPanel({ onClose }) {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({
    email: "",
    display_name: "",
    password: "",
    role: "analyst",
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadUsers = useCallback(async () => {
    try {
      const result = await apiRequest("/api/v1/auth/users");
      setUsers(result.users || []);
    } catch (err) {
      setError(err.message || "Could not load accounts.");
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  async function createUser(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiRequest("/api/v1/auth/users", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm({ email: "", display_name: "", password: "", role: "analyst" });
      setMessage("Account created. Add the user to a project and assign their project role.");
      await loadUsers();
    } catch (err) {
      setError(err.message || "Could not create account.");
    } finally {
      setBusy(false);
    }
  }

  async function updateUser(user, changes) {
    setError("");
    setMessage("");
    try {
      await apiRequest(`/api/v1/auth/users/${user.user_id}`, {
        method: "PATCH",
        body: JSON.stringify(changes),
      });
      setMessage("Account updated.");
      await loadUsers();
    } catch (err) {
      setError(err.message || "Could not update account.");
    }
  }

  return (
    <section className="auth-admin-panel">
      <div className="auth-panel-heading">
        <div>
          <div className="auth-eyebrow">ADMINISTRATION</div>
          <h2>Manage accounts</h2>
          <p>Create accounts for the team and assign a default job area.</p>
        </div>
        <button className="auth-secondary-button" onClick={onClose}>Close</button>
      </div>

      <form className="auth-user-form" onSubmit={createUser}>
        <label>
          Full name
          <input
            value={form.display_name}
            onChange={(event) => setForm({ ...form, display_name: event.target.value })}
            required
            maxLength={120}
            autoComplete="name"
          />
        </label>
        <label>
          Email
          <input
            type="email"
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
            required
            autoComplete="off"
          />
        </label>
        <label>
          Temporary password
          <input
            type="password"
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            required
            minLength={12}
            maxLength={256}
            autoComplete="new-password"
          />
        </label>
        <label>
          Default job area
          <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
            {ROLE_OPTIONS.map((role) => <option key={role} value={role}>{role}</option>)}
          </select>
        </label>
        <button className="auth-primary-button" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>

      {message && <p className="auth-success" role="status">{message}</p>}
      {error && <p className="auth-error" role="alert">{error}</p>}

      <div className="auth-user-list">
        {users.map((user) => (
          <div className="auth-user-row" key={user.user_id}>
            <div>
              <strong>{user.display_name}</strong>
              <span>{user.email}</span>
              <small>{user.is_active ? "Active" : "Disabled"}</small>
            </div>
            <div className="auth-user-actions">
              <select
                aria-label={`Role for ${user.email}`}
                value={user.role}
                onChange={(event) => updateUser(user, { role: event.target.value })}
              >
                {ROLE_OPTIONS.map((role) => <option key={role} value={role}>{role}</option>)}
              </select>
              <button
                className="auth-secondary-button"
                onClick={() => updateUser(user, { is_active: !user.is_active })}
              >
                {user.is_active ? "Disable" : "Enable"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function AuthGate({ children }) {
  const [status, setStatus] = useState("checking");
  const [user, setUser] = useState(null);
  const [setup, setSetup] = useState({
    needs_bootstrap: false,
    bootstrap_configured: false,
  });
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    email: "",
    password: "",
    display_name: "",
    bootstrap_token: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showAccounts, setShowAccounts] = useState(false);

  const refreshSession = useCallback(async () => {
    try {
      const result = await apiRequest("/api/v1/auth/me");
      setUser(result.user);
      setStatus("authenticated");
    } catch {
      setUser(null);
      try {
        const setupInfo = await apiRequest("/api/v1/auth/setup-status");
        setSetup(setupInfo);
      } catch {
        setSetup({ needs_bootstrap: false, bootstrap_configured: false });
      }
      setStatus("unauthenticated");
    }
  }, []);

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const endpoint = mode === "bootstrap"
        ? "/api/v1/auth/bootstrap"
        : "/api/v1/auth/login";
      const body = mode === "bootstrap"
        ? {
            email: form.email,
            display_name: form.display_name,
            password: form.password,
            bootstrap_token: form.bootstrap_token,
          }
        : { email: form.email, password: form.password };
      const result = await apiRequest(endpoint, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setUser(result.user);
      setStatus("authenticated");
      setForm({ email: "", password: "", display_name: "", bootstrap_token: "" });
    } catch (err) {
      setError(err.message || "Could not authenticate.");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    try {
      await apiRequest("/api/v1/auth/logout", { method: "POST" });
    } catch {
      // Clear the UI even if the session has already expired on the server.
    }
    setUser(null);
    setShowAccounts(false);
    setStatus("unauthenticated");
    try {
      setSetup(await apiRequest("/api/v1/auth/setup-status"));
    } catch {
      setSetup({ needs_bootstrap: false, bootstrap_configured: false });
    }
  }

  if (status === "checking") {
    return <div className="auth-loading-screen"><div className="auth-spinner" />Checking your Specra session…</div>;
  }

  if (status === "authenticated" && user) {
    return (
      <div className="auth-app-frame">
        <div className="auth-session-bar">
          <div className="auth-session-identity">
            <span className="auth-avatar">{(user.display_name || "S").slice(0, 1).toUpperCase()}</span>
            <span className="auth-session-name">{user.display_name}</span>
            <span className="auth-role-chip">{user.role}</span>
          </div>
          <div className="auth-session-actions">
            {user.role === "admin" && (
              <button className="auth-secondary-button" onClick={() => setShowAccounts((value) => !value)}>
                {showAccounts ? "Close accounts" : "Manage accounts"}
              </button>
            )}
            <button className="auth-logout-button" onClick={logout}>Sign out</button>
          </div>
        </div>
        {showAccounts && user.role === "admin" && <AdminAccountsPanel onClose={() => setShowAccounts(false)} />}
        {typeof children === "function" ? children({ user }) : children}
      </div>
    );
  }

  const showBootstrap = setup.needs_bootstrap && setup.bootstrap_configured;
  const bootstrapBlocked = setup.needs_bootstrap && !setup.bootstrap_configured;
  const activeMode = showBootstrap ? mode : "login";

  return (
    <main className="auth-screen">
      <section className="auth-card">
        <div className="auth-brand">
          <div className="auth-brand-mark">S</div>
          <div>
            <div className="auth-brand-name">Specra</div>
            <div className="auth-brand-subtitle">AI Software Engineering Studio</div>
          </div>
        </div>

        <div className="auth-eyebrow">{showBootstrap && activeMode === "bootstrap" ? "INITIAL SETUP" : "SECURE WORKSPACE"}</div>
        <h1>{showBootstrap && activeMode === "bootstrap" ? "Create the first admin" : "Welcome back"}</h1>
        <p className="auth-intro">
          {showBootstrap && activeMode === "bootstrap"
            ? "Use the one-time setup token configured on the backend. The first account becomes the workspace administrator."
            : "Sign in with the account provided by your Specra administrator."}
        </p>

        {bootstrapBlocked && (
          <div className="auth-notice">
            The initial admin has not been created. Set <code>AUTH_BOOTSTRAP_TOKEN</code> in the backend environment, then refresh this page to initialize the workspace.
          </div>
        )}

        <form className="auth-login-form" onSubmit={submit}>
          {showBootstrap && activeMode === "bootstrap" && (
            <>
              <label>
                Display name
                <input
                  value={form.display_name}
                  onChange={(event) => setForm({ ...form, display_name: event.target.value })}
                  required
                  maxLength={120}
                  autoComplete="name"
                />
              </label>
              <label>
                One-time setup token
                <input
                  type="password"
                  value={form.bootstrap_token}
                  onChange={(event) => setForm({ ...form, bootstrap_token: event.target.value })}
                  required
                  autoComplete="off"
                />
              </label>
            </>
          )}
          <label>
            Email address
            <input
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              required
              autoComplete="username"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              required
              minLength={activeMode === "bootstrap" ? 12 : 1}
              maxLength={256}
              autoComplete={activeMode === "bootstrap" ? "new-password" : "current-password"}
            />
          </label>
          <button className="auth-primary-button" disabled={busy || bootstrapBlocked}>
            {busy ? "Please wait…" : activeMode === "bootstrap" ? "Create administrator" : "Sign in"}
          </button>
        </form>

        {error && <p className="auth-error" role="alert">{error}</p>}

        {showBootstrap && (
          <button
            className="auth-mode-switch"
            type="button"
            onClick={() => {
              setError("");
              setMode((value) => value === "bootstrap" ? "login" : "bootstrap");
            }}
          >
            {activeMode === "bootstrap" ? "Already have an account? Sign in" : "Initialize Specra for the first time"}
          </button>
        )}

        <div className="auth-security-note">
          Your session is stored in an HttpOnly cookie. Accounts and project roles are managed by an administrator.
        </div>
      </section>
    </main>
  );
}
