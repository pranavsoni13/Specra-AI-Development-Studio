import { useCallback, useEffect, useRef, useState } from "react";

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

export default function ProjectCopilotPanel({
  projectId,
  onClose,
  onUseSuggestion,
}) {
  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState("");
  const [question, setQuestion] = useState("");
  const [myRole, setMyRole] = useState("");
  const [canAsk, setCanAsk] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const messageEndRef = useRef(null);

  const baseUrl = `/api/v1/projects/${encodeURIComponent(projectId)}/copilot`;

  const loadConversationList = useCallback(async () => {
    try {
      const data = await apiRequest(baseUrl);
      setConversations(data.conversations || []);
      setMyRole(data.my_role || "");
      setCanAsk(Boolean(data.can_ask));
      return data.conversations || [];
    } catch (err) {
      setError(err.message || "Could not load Copilot history.");
      return [];
    }
  }, [baseUrl]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setMessages([]);
    setConversationId("");
    try {
      const list = await loadConversationList();
      if (list.length) {
        const latest = list[0];
        const data = await apiRequest(`${baseUrl}/${encodeURIComponent(latest.conversation_id)}`);
        setConversationId(latest.conversation_id);
        setMessages(data.conversation?.messages || []);
      }
    } catch (err) {
      setError(err.message || "Could not load Copilot.");
    } finally {
      setLoading(false);
    }
  }, [baseUrl, loadConversationList]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  async function openConversation(id) {
    setError("");
    setLoading(true);
    try {
      const data = await apiRequest(`${baseUrl}/${encodeURIComponent(id)}`);
      setConversationId(id);
      setMessages(data.conversation?.messages || []);
    } catch (err) {
      setError(err.message || "Could not open that conversation.");
    } finally {
      setLoading(false);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    const clean = question.trim();
    if (!clean || sending || !canAsk) return;
    setSending(true);
    setError("");
    try {
      const body = { message: clean };
      if (conversationId) body.conversation_id = conversationId;
      const data = await apiRequest(`${baseUrl}/ask`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setConversationId(data.conversation.conversation_id);
      setMessages(data.conversation.messages || []);
      setQuestion("");
      const list = await loadConversationList();
      if (!list.some((item) => item.conversation_id === data.conversation.conversation_id)) {
        setConversations((previous) => [
          {
            conversation_id: data.conversation.conversation_id,
            title: data.conversation.title,
            created_at: data.conversation.created_at,
            updated_at: data.conversation.updated_at,
            message_count: data.conversation.messages?.length || 0,
          },
          ...previous,
        ]);
      }
    } catch (err) {
      setError(err.message || "Copilot could not answer this question.");
    } finally {
      setSending(false);
    }
  }

  function newConversation() {
    setConversationId("");
    setMessages([]);
    setQuestion("");
    setError("");
  }

  async function deleteConversation(id) {
    const confirmed = window.confirm("Delete this private Copilot conversation?");
    if (!confirmed) return;
    setError("");
    try {
      await apiRequest(`${baseUrl}/${encodeURIComponent(id)}`, { method: "DELETE" });
      const next = conversations.filter((item) => item.conversation_id !== id);
      setConversations(next);
      if (conversationId === id) {
        setConversationId("");
        setMessages([]);
        if (next.length) await openConversation(next[0].conversation_id);
      }
    } catch (err) {
      setError(err.message || "Could not delete the conversation.");
    }
  }

  return (
    <section className="copilot-panel">
      <div className="copilot-heading">
        <div className="copilot-brand">
          <div className="copilot-brand-icon">✳</div>
          <div>
            <div className="auth-eyebrow">PROJECT-AWARE GENAI</div>
            <h2>Specra Copilot</h2>
            <p>Ask about the current brief, requirements, plan, architecture, review, and saved context.</p>
          </div>
        </div>
        <button className="auth-secondary-button" onClick={onClose}>Close</button>
      </div>

      <div className="copilot-layout">
        <aside className="copilot-sidebar">
          <button className="auth-primary-button copilot-new-chat" onClick={newConversation}>
            + New conversation
          </button>
          <div className="copilot-sidebar-label">Your project chats</div>
          {conversations.length === 0 ? (
            <p className="copilot-no-chats">Your questions will appear here.</p>
          ) : (
            <div className="copilot-conversation-list">
              {conversations.map((item) => (
                <div
                  key={item.conversation_id}
                  className={`copilot-conversation ${conversationId === item.conversation_id ? "active" : ""}`}
                >
                  <button
                    className="copilot-conversation-open"
                    onClick={() => openConversation(item.conversation_id)}
                    title={item.title}
                  >
                    <span>{item.title}</span>
                    <small>{item.message_count} messages</small>
                  </button>
                  <button
                    className="copilot-delete-chat"
                    onClick={() => deleteConversation(item.conversation_id)}
                    aria-label={`Delete conversation: ${item.title}`}
                    title="Delete conversation"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="copilot-role-note">
            Project role: <strong>{myRole || "checking…"}</strong>
          </div>
        </aside>

        <div className="copilot-chat-column">
          <div className="copilot-messages" aria-live="polite">
            {loading ? (
              <div className="copilot-empty">Loading your project conversations…</div>
            ) : messages.length === 0 ? (
              <div className="copilot-empty copilot-welcome">
                <div className="copilot-welcome-icon">✳</div>
                <h3>Think through your project with Specra</h3>
                <p>Ask why an architecture decision was made, identify requirement gaps, or request a proposed change.</p>
                <div className="copilot-suggestions">
                  {[
                    "Summarize the current project and its biggest risks.",
                    "Which requirements are not clearly covered by the architecture?",
                    "Suggest improvements without changing any saved artifacts.",
                  ].map((prompt) => (
                    <button key={prompt} onClick={() => setQuestion(prompt)} disabled={!canAsk}>
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <article className={`copilot-message ${message.role === "user" ? "from-user" : "from-assistant"}`} key={message.message_id}>
                  <div className="copilot-message-role">
                    {message.role === "user" ? "YOU" : "SPEC­RA COPILOT"}
                    {message.model_name && <span>{message.model_name}</span>}
                  </div>
                  <div className="copilot-message-content">{message.content}</div>

                  {message.role === "assistant" && message.source_refs?.length > 0 && (
                    <div className="copilot-source-list">
                      <strong>Project evidence used</strong>
                      <div className="copilot-source-chips">
                        {message.source_refs.map((source) => (
                          <span className="copilot-source-chip" key={source.source_id} title={source.source_id}>
                            {source.title}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {message.role === "assistant" && message.proposed_changes?.length > 0 && (
                    <div className="copilot-change-list">
                      <strong>Proposed changes — nothing has been saved yet</strong>
                      {message.proposed_changes.map((proposal, index) => (
                        <div className="copilot-change-card" key={`${message.message_id}-${index}`}>
                          <div className="copilot-change-meta">
                            <span>{proposal.target_artifact.replace("_", " ")}</span>
                          </div>
                          <h4>{proposal.summary}</h4>
                          <p>{proposal.rationale}</p>
                          <div className="copilot-change-instruction">
                            <span>Suggested refinement instruction</span>
                            <p>{proposal.suggested_instruction}</p>
                          </div>
                          <button
                            className="auth-secondary-button"
                            onClick={() => onUseSuggestion?.(proposal)}
                          >
                            Review in refinement panel
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              ))
            )}
            {sending && (
              <div className="copilot-thinking">
                <span className="copilot-thinking-dot" />
                <span>Checking project context and preparing an answer…</span>
              </div>
            )}
            <div ref={messageEndRef} />
          </div>

          {error && <p className="auth-error copilot-error" role="alert">{error}</p>}

          <form className="copilot-composer" onSubmit={sendMessage}>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={canAsk ? "Ask about this project… (Enter to send, Shift+Enter for a new line)" : "Your current project role is read-only for Copilot."}
              rows={3}
              maxLength={8000}
              disabled={!canAsk || sending}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <div className="copilot-composer-footer">
              <span>Project-scoped context · suggestions require approval</span>
              <button className="auth-primary-button" type="submit" disabled={!canAsk || sending || !question.trim()}>
                {sending ? "Thinking…" : "Ask Specra"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </section>
  );
}
