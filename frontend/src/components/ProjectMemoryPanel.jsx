import { useCallback, useEffect, useState } from "react";

export default function ProjectMemoryPanel({ apiBase, projectId, onClose }) {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("note");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const contextUrl = `${apiBase}/projects/${projectId}/context`;

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(contextUrl);
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Could not load project memory.");
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load project memory.");
    } finally {
      setLoading(false);
    }
  }, [contextUrl]);

  useEffect(() => { loadItems(); }, [loadItems]);

  async function saveSource(event) {
    event.preventDefault();
    if (!name.trim() || !content.trim() || saving) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(contextUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), kind, content: content.trim(), metadata: {} }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Could not save this memory source.");
      setName(""); setKind("note"); setContent("");
      setNotice("Saved. This source will be used during the next full workflow.");
      await loadItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this memory source.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteSource(item) {
    if (!window.confirm(`Delete the memory source "${item.name}"?`)) return;
    setError(""); setNotice("");
    try {
      const response = await fetch(`${contextUrl}/${encodeURIComponent(item.context_id)}`, { method: "DELETE" });
      if (!response.ok) {
        let message = "Could not delete this memory source.";
        try { const data = await response.json(); message = data?.detail || message; } catch { /* empty DELETE response */ }
        throw new Error(message);
      }
      setNotice("Memory source deleted.");
      await loadItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this memory source.");
    }
  }

  return (
    <section className="project-memory-panel" aria-label="Project memory">
      <div className="project-memory-heading">
        <div>
          <div className="memory-eyebrow">PROJECT CONTEXT</div>
          <h2>Project Memory</h2>
          <p>Save notes, constraints, design decisions, reference text, or code excerpts. The next full workflow sends saved sources to Requirement Analysis.</p>
        </div>
        <button type="button" className="secondary-button" onClick={onClose}>Close</button>
      </div>

      <div className="memory-grid">
        <form className="memory-form" onSubmit={saveSource}>
          <h3>Add a memory source</h3>
          <label>Source name
            <input value={name} onChange={(event) => setName(event.target.value)} maxLength={200} placeholder="e.g. Product constraints" required disabled={saving}/>
          </label>
          <label>Source type
            <select value={kind} onChange={(event) => setKind(event.target.value)} disabled={saving}>
              <option value="note">Note</option>
              <option value="requirements">Requirements</option>
              <option value="constraints">Constraints</option>
              <option value="design">Design decision</option>
              <option value="reference">Reference</option>
              <option value="code">Code excerpt</option>
            </select>
          </label>
          <label>Content
            <textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="Add facts or constraints future agents should consider..." rows={6} required disabled={saving}/>
          </label>
          <button type="submit" className="primary-button" disabled={saving || !name.trim() || !content.trim()}>{saving ? "Saving..." : "Save to Project Memory"}</button>
          <p className="memory-note">Existing artifacts do not change immediately. Click <strong>Run All Again</strong> after saving memory.</p>
        </form>

        <div className="memory-sources">
          <div className="memory-sources-heading">
            <h3>Saved sources ({items.length})</h3>
            <button type="button" className="secondary-button" onClick={loadItems} disabled={loading}>Refresh</button>
          </div>
          {loading ? <p className="memory-empty">Loading project memory...</p> :
            items.length === 0 ? <p className="memory-empty">No memory sources yet. Add a note or reference on the left.</p> :
            <div className="memory-source-list">
              {items.map((item) => (
                <article className="memory-source-card" key={item.context_id}>
                  <div className="memory-source-title-row">
                    <div><h4>{item.name}</h4><span className="memory-source-kind">{item.kind}</span></div>
                    <button type="button" className="memory-delete-button" onClick={() => deleteSource(item)} title={`Delete ${item.name}`}>Delete</button>
                  </div>
                  <details><summary>View source content</summary><pre>{item.content}</pre></details>
                </article>
              ))}
            </div>
          }
        </div>
      </div>
      {notice && <div className="memory-notice" role="status">{notice}</div>}
      {error && <div className="memory-error" role="alert">{error}</div>}
    </section>
  );
}
