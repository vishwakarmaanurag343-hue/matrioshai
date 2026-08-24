import React, { useState, useEffect } from "react";
import {
  Mail,
  Send,
  MessageSquare,
  Sparkles,
  StopCircle,
  CheckCircle,
  AlertTriangle
} from "lucide-react";
import { communicationApi } from "../../services/api/communication";
import {
  CommunicationProviderStatus,
  CommunicationConversation,
  ReplySuggestion,
  ConversationSummary
} from "../../types";

export const CommunicationView: React.FC = () => {
  const [providers, setProviders] = useState<CommunicationProviderStatus[]>([]);
  const [conversations, setConversations] = useState<CommunicationConversation[]>([]);
  const [activeConv, setActiveConv] = useState<CommunicationConversation | null>(null);
  const [messageInput, setMessageInput] = useState("");
  const [replySuggestions, setReplySuggestions] = useState<ReplySuggestion | null>(null);
  const [summary, setSummary] = useState<ConversationSummary | null>(null);
  const [pendingConfirmationId, setPendingConfirmationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [provList, convList] = await Promise.all([
        communicationApi.getProviders(),
        communicationApi.listConversations(),
      ]);
      setProviders(provList);
      setConversations(convList);
      if (convList.length > 0 && !activeConv) {
        selectConversation(convList[0]);
      }
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const selectConversation = async (conv: CommunicationConversation) => {
    setActiveConv(conv);
    setPendingConfirmationId(null);
    setReplySuggestions(null);
    setSummary(null);
    try {
      const [sum, rep] = await Promise.all([
        communicationApi.summarizeConversation(conv.id),
        communicationApi.generateReplies(conv.id),
      ]);
      setSummary(sum);
      setReplySuggestions(rep);
    } catch (e) {
      // transient summary error
    }
  };

  const handleRequestSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeConv || !messageInput.trim()) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await communicationApi.requestSend({
        provider: activeConv.provider,
        conversation_id: activeConv.id,
        recipient: activeConv.participants[0] || "Recipient",
        text: messageInput.trim(),
      });
      if (res.status === "CONFIRMATION_REQUIRED") {
        setPendingConfirmationId(res.id);
      }
    } catch (e: any) {
      setErrorMsg(`Send request failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveSend = async () => {
    if (!activeConv || !pendingConfirmationId) return;
    setLoading(true);
    try {
      await communicationApi.approveSend(pendingConfirmationId, {
        provider: activeConv.provider,
        conversation_id: activeConv.id,
        recipient: activeConv.participants[0] || "Recipient",
        text: messageInput.trim(),
      });
      setSuccessMsg("Message sent successfully!");
      setPendingConfirmationId(null);
      setMessageInput("");
      await loadData();
    } catch (e: any) {
      setErrorMsg(`Approval failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleEmergencyStop = async () => {
    try {
      await communicationApi.emergencyStop();
      setPendingConfirmationId(null);
      setErrorMsg("COMMUNICATION SENDS EMERGENCY STOPPED");
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Top Header */}
      <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Mail size={20} color="var(--accent-primary)" />
          <h2 style={{ fontSize: "16px", fontWeight: 700 }}>Personal Workspace & Communication Intelligence</h2>
        </div>
        <button
          onClick={handleEmergencyStop}
          style={{ background: "var(--status-red)", color: "#fff", border: "none", padding: "6px 14px", borderRadius: "6px", fontSize: "12px", fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
        >
          <StopCircle size={14} /> STOP SENDS
        </button>
      </div>

      {errorMsg && (
        <div style={{ padding: "8px 16px", background: "rgba(239, 68, 68, 0.15)", color: "var(--status-red)", fontSize: "12px" }}>
          {errorMsg}
        </div>
      )}
      {successMsg && (
        <div style={{ padding: "8px 16px", background: "rgba(16, 185, 129, 0.15)", color: "var(--status-green)", fontSize: "12px" }}>
          {successMsg}
        </div>
      )}

      {/* Main 3-Pane Split: Left (Inbox & Providers) | Center (Active Thread & Composer) | Right (AI Assistant) */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Left Pane: Providers & Conversations */}
        <div style={{ width: "280px", borderRight: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", flexDirection: "column" }}>
          {/* Provider status tags */}
          <div style={{ padding: "10px", borderBottom: "1px solid var(--border-color)", display: "flex", gap: "6px", flexWrap: "wrap" }}>
            {providers.map((p) => (
              <span key={p.provider} style={{ fontSize: "10px", fontWeight: 700, padding: "2px 6px", borderRadius: "4px", background: "var(--bg-tertiary)", color: p.connected ? "var(--status-green)" : "var(--text-muted)" }}>
                ● {p.provider.toUpperCase()}
              </span>
            ))}
          </div>

          {/* Conversations list */}
          <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
            <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", marginBottom: "8px" }}>UNIFIED INBOX</div>
            {conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => selectConversation(c)}
                style={{
                  padding: "10px",
                  borderRadius: "6px",
                  background: activeConv?.id === c.id ? "var(--bg-tertiary)" : "transparent",
                  cursor: "pointer",
                  marginBottom: "4px",
                  border: activeConv?.id === c.id ? "1px solid var(--accent-primary)" : "1px solid transparent"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "2px" }}>
                  <strong style={{ fontSize: "12px" }}>{c.title}</strong>
                  {c.unread_count > 0 && (
                    <span style={{ fontSize: "10px", background: "var(--accent-primary)", color: "#fff", padding: "1px 5px", borderRadius: "10px" }}>
                      {c.unread_count}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  {c.provider.toUpperCase()} | {c.participants.join(", ")}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Center Pane: Active Conversation & Composer */}
        <div style={{ flex: 2, display: "flex", flexDirection: "column", background: "var(--bg-primary)" }}>
          {activeConv ? (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
              {/* Active Thread Header */}
              <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-secondary)", fontSize: "13px", fontWeight: 700 }}>
                {activeConv.title} ({activeConv.provider.toUpperCase()})
              </div>

              {/* Messages stream */}
              <div style={{ flex: 1, padding: "16px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "10px" }}>
                {activeConv.recent_messages.map((m) => (
                  <div
                    key={m.id}
                    style={{
                      alignSelf: m.direction === "OUTGOING" ? "flex-end" : "flex-start",
                      maxWidth: "75%",
                      background: m.direction === "OUTGOING" ? "var(--accent-primary)" : "var(--bg-secondary)",
                      color: m.direction === "OUTGOING" ? "#fff" : "var(--text-primary)",
                      padding: "10px 14px",
                      borderRadius: "8px",
                      fontSize: "12px",
                      lineHeight: "1.4"
                    }}
                  >
                    <div style={{ fontSize: "10px", opacity: 0.8, marginBottom: "2px" }}>{m.sender}</div>
                    <div>{m.text}</div>
                  </div>
                ))}
              </div>

              {/* Tier 2 Exact Send Approval Modal Card */}
              {pendingConfirmationId && (
                <div style={{ margin: "0 16px 12px 16px", padding: "12px", background: "rgba(245, 158, 11, 0.1)", border: "1px solid var(--status-amber)", borderRadius: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--status-amber)", fontWeight: 700, fontSize: "12px", marginBottom: "6px" }}>
                    <AlertTriangle size={14} /> Tier 2 Message Send Authorization Required
                  </div>
                  <div style={{ fontSize: "12px", marginBottom: "8px" }}>
                    Confirm sending this exact message to <strong>{activeConv.participants[0]}</strong> via <strong>{activeConv.provider.toUpperCase()}</strong>:
                  </div>
                  <pre style={{ margin: "4px 0 10px 0", padding: "8px", background: "var(--bg-secondary)", borderRadius: "4px", fontSize: "12px", color: "var(--text-primary)" }}>
                    {messageInput}
                  </pre>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <button className="new-chat-btn" onClick={handleApproveSend} disabled={loading} style={{ fontSize: "11px", padding: "5px 12px" }}>
                      <CheckCircle size={13} /> Approve & Send
                    </button>
                    <button className="action-btn" onClick={() => setPendingConfirmationId(null)} style={{ fontSize: "11px", padding: "5px 12px" }}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Composer Form */}
              <form onSubmit={handleRequestSend} style={{ padding: "12px 16px", borderTop: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", gap: "8px" }}>
                <input
                  type="text"
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  placeholder="Draft message (e.g. Thanks, I'll review and get back to you)..."
                  style={{ flex: 1, background: "var(--bg-tertiary)", border: "1px solid var(--border-color)", padding: "8px 12px", borderRadius: "6px", color: "var(--text-primary)", fontSize: "12px", outline: "none" }}
                  disabled={loading}
                />
                <button type="submit" className="new-chat-btn" disabled={loading || !messageInput.trim()} style={{ fontSize: "12px", padding: "8px 14px", gap: "6px" }}>
                  <Send size={13} /> Send
                </button>
              </form>
            </div>
          ) : (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "13px" }}>
              Select a conversation on the left.
            </div>
          )}
        </div>

        {/* Right Pane: AI Assistant (Summary & Suggested Replies) */}
        <div style={{ width: "320px", borderLeft: "1px solid var(--border-color)", background: "var(--bg-secondary)", padding: "14px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* Summary Card */}
          <div style={{ background: "var(--bg-tertiary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "12px" }}>
            <h3 style={{ fontSize: "13px", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
              <MessageSquare size={14} color="var(--accent-primary)" /> Conversation Summary
            </h3>
            {summary ? (
              <div style={{ fontSize: "12px", lineHeight: "1.4" }}>
                <div style={{ marginBottom: "6px" }}>{summary.summary}</div>
                {summary.action_items.length > 0 && (
                  <div>
                    <strong>Action Items:</strong>
                    <ul style={{ margin: "4px 0", paddingLeft: "16px" }}>
                      {summary.action_items.map((act, i) => <li key={i}>{act}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ color: "var(--text-muted)", fontSize: "12px" }}>No summary available</div>
            )}
          </div>

          {/* Reply Suggestions Card */}
          <div style={{ flex: 1, background: "var(--bg-tertiary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "12px" }}>
            <h3 style={{ fontSize: "13px", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
              <Sparkles size={14} color="var(--accent-primary)" /> AI Reply Suggestions
            </h3>
            {replySuggestions && replySuggestions.options.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {replySuggestions.options.map((opt, i) => (
                  <div
                    key={i}
                    onClick={() => setMessageInput(opt.reply_text)}
                    style={{
                      padding: "8px",
                      background: "var(--bg-secondary)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "6px",
                      fontSize: "11px",
                      cursor: "pointer"
                    }}
                    title="Click to load draft"
                  >
                    <strong style={{ color: "var(--accent-primary)" }}>{opt.style}:</strong>
                    <div style={{ marginTop: "2px", color: "var(--text-primary)" }}>{opt.reply_text}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: "var(--text-muted)", fontSize: "12px" }}>No suggestions generated</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
