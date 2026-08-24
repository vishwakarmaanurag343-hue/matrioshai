import React, { useState, useEffect, useRef } from "react";
import { Mic, ArrowUp, Paperclip } from "lucide-react";
import { Message } from "../../types";
import { conversationApi } from "../../services/api/conversations";
import { chatApi } from "../../services/api/chat";

interface ChatViewProps {
  activeConversationId: string | null;
  onConversationCreated?: (convId: string) => void;
}

export const ChatView: React.FC<ChatViewProps> = ({
  activeConversationId,
  onConversationCreated,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [activeRole, setActiveRole] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId);
    } else {
      setMessages([]);
    }
  }, [activeConversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const loadMessages = async (id: string) => {
    try {
      const conv = await conversationApi.get(id);
      setMessages(conv.messages || []);
    } catch (e) {
      console.error("Failed to load messages", e);
    }
  };

  const handleSend = async (customPrompt?: string) => {
    const textToSend = (customPrompt || input).trim();
    if (!textToSend || isLoading) return;

    setInput("");
    setIsLoading(true);

    const fullPrompt = activeRole ? `@${activeRole} ${textToSend}` : textToSend;

    // Optimistic UI for user message
    const tempUserMsg: Message = {
      id: "temp_user_" + Date.now(),
      conversation_id: activeConversationId || "new",
      role: "user",
      content: textToSend,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    let streamingContent = "";
    const tempAsstId = "temp_asst_" + Date.now();

    chatApi.sendStream(
      fullPrompt,
      activeConversationId || undefined,
      (chunk) => {
        streamingContent += chunk;
        setMessages((prev) => {
          const filtered = prev.filter((m) => m.id !== tempAsstId);
          return [
            ...filtered,
            {
              id: tempAsstId,
              conversation_id: activeConversationId || "new",
              role: "assistant",
              content: streamingContent,
              created_at: new Date().toISOString(),
            },
          ];
        });
      },
      () => {
        setIsLoading(false);
        if (!activeConversationId && onConversationCreated) {
          conversationApi.list().then((convs) => {
            if (convs.length > 0) onConversationCreated(convs[0].id);
          });
        }
      },
      (err) => {
        setIsLoading(false);
        setMessages((prev) => [
          ...prev,
          {
            id: "err_" + Date.now(),
            conversation_id: activeConversationId || "new",
            role: "assistant",
            content: `⚠️ ${err}`,
            created_at: new Date().toISOString(),
          },
        ]);
      }
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const roles = ["CEO", "CTO", "CFO", "COO", "CIO"];

  return (
    <div style={{ flex: 1, height: "100%", display: "flex", flexDirection: "column", position: "relative", overflow: "hidden" }}>
      {/* If No Messages: Center Stage Landing View */}
      {messages.length === 0 ? (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 20px" }}>
          
          {/* Logo & Title */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: "40px" }}>
            {/* Matrioshai Logo SVG */}
            <svg width="68" height="68" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M28 65C32.4183 65 36 61.4183 36 57C36 52.5817 32.4183 49 28 49C23.5817 49 20 52.5817 20 57C20 61.4183 23.5817 65 28 65Z" fill="black"/>
              <path d="M42 42C48.6274 42 54 36.6274 54 30C54 23.3726 48.6274 18 42 18C35.3726 18 30 23.3726 30 30C30 36.6274 35.3726 42 42 42Z" fill="black"/>
              <path d="M68 62C72.4183 62 76 58.4183 76 54C76 49.5817 72.4183 46 68 46C63.5817 46 60 49.5817 60 54C60 58.4183 63.5817 62 68 62Z" fill="black"/>
              <path d="M65 32C68.3137 32 71 29.3137 71 26C71 22.6863 68.3137 20 65 20C61.6863 20 59 22.6863 59 26C59 29.3137 61.6863 32 65 32Z" fill="black"/>
              <path d="M48 68C56 68 62 58 62 48C62 38 52 30 42 30C32 30 24 40 24 50C24 60 38 68 48 68Z" stroke="black" strokeWidth="12" strokeLinecap="round"/>
            </svg>

            <h1 style={{ fontSize: "16px", fontWeight: 800, letterSpacing: "3px", color: "var(--text-primary)", marginTop: "16px" }}>
              MATRIOSHAI
            </h1>
            <div style={{ fontSize: "9px", fontWeight: 600, letterSpacing: "6px", color: "var(--text-muted)", marginTop: "8px", textTransform: "uppercase" }}>
              PARADOX OF INTELLIGENCE
            </div>
          </div>

          {/* Floating Pill Input Box */}
          <div style={{ width: "100%", maxWidth: "620px", position: "relative" }}>
            <div
              style={{
                background: "var(--bg-card)",
                borderRadius: "24px",
                border: "1px solid rgba(0, 0, 0, 0.08)",
                boxShadow: "0 10px 30px rgba(0, 0, 0, 0.06)",
                padding: "16px 20px 14px 20px",
                display: "flex",
                flexDirection: "column",
                gap: "12px",
              }}
            >
              <input
                type="text"
                placeholder="Lets do work dude..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                style={{
                  width: "100%",
                  border: "none",
                  outline: "none",
                  fontSize: "14px",
                  color: "var(--text-primary)",
                  background: "transparent",
                }}
              />

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                {/* Deep Research Pill */}
                <div
                  onClick={() => setInput((p) => (p ? `Research: ${p}` : "Deep Research: "))}
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "var(--text-muted)",
                    background: "var(--bg-card-secondary)",
                    padding: "4px 10px",
                    borderRadius: "var(--radius-pill)",
                    cursor: "pointer",
                    border: "1px solid rgba(0, 0, 0, 0.04)",
                  }}
                >
                  Deep Research
                </div>

                {/* Mic & Send Buttons */}
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <button
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "var(--text-muted)",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Mic size={16} />
                  </button>

                  <button
                    onClick={() => handleSend()}
                    style={{
                      width: "28px",
                      height: "28px",
                      borderRadius: "50%",
                      background: "#3a3a3c",
                      border: "none",
                      color: "#ffffff",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      cursor: "pointer",
                    }}
                  >
                    <ArrowUp size={14} />
                  </button>
                </div>
              </div>
            </div>

            {/* Attach File Under-pill */}
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                marginTop: "8px",
                paddingRight: "16px",
                fontSize: "11px",
                color: "var(--text-muted)",
                cursor: "pointer",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <Paperclip size={12} /> Attach file
              </span>
            </div>
          </div>

          {/* Role Selectors: What you want to be today ? */}
          <div style={{ marginTop: "32px", display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 500 }}>
              What you want to be today ?
            </span>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", justifyContent: "center" }}>
              {roles.map((r) => (
                <button
                  key={r}
                  onClick={() => setActiveRole((prev) => (prev === r ? null : r))}
                  style={{
                    background: activeRole === r ? "#000000" : "var(--bg-card-secondary)",
                    color: activeRole === r ? "#ffffff" : "var(--text-secondary)",
                    border: "1px solid rgba(0, 0, 0, 0.05)",
                    padding: "6px 16px",
                    borderRadius: "var(--radius-pill)",
                    fontSize: "11px",
                    fontWeight: 700,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {r}
                </button>
              ))}
              <button
                onClick={() => setActiveRole("5C")}
                style={{
                  background: activeRole === "5C" ? "#000000" : "var(--bg-card-secondary)",
                  color: activeRole === "5C" ? "#ffffff" : "var(--text-secondary)",
                  border: "1px solid rgba(0, 0, 0, 0.05)",
                  padding: "6px 14px",
                  borderRadius: "var(--radius-pill)",
                  fontSize: "11px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                +
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Active Conversation Stream */
        <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
          <div style={{ flex: 1, overflowY: "auto", padding: "24px 30px", display: "flex", flexDirection: "column", gap: "16px" }}>
            {messages.map((m) => (
              <div
                key={m.id}
                style={{
                  display: "flex",
                  justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    maxWidth: "75%",
                    padding: "12px 18px",
                    borderRadius: "18px",
                    background: m.role === "user" ? "#000000" : "var(--bg-card-secondary)",
                    color: m.role === "user" ? "#ffffff" : "var(--text-primary)",
                    fontSize: "13px",
                    lineHeight: "1.5",
                    boxShadow: "0 2px 8px rgba(0, 0, 0, 0.04)",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div style={{ display: "flex", justifyContent: "flex-start" }}>
                <div style={{ padding: "10px 16px", borderRadius: "16px", background: "var(--bg-card-secondary)", fontSize: "12px", color: "var(--text-muted)" }}>
                  Thinking...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Stream Input */}
          <div style={{ padding: "16px 30px", borderTop: "1px solid var(--border-light)", display: "flex", gap: "10px", alignItems: "center" }}>
            <input
              type="text"
              placeholder="Lets do work dude..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              style={{
                flex: 1,
                background: "var(--bg-card-secondary)",
                border: "1px solid var(--border-light)",
                borderRadius: "var(--radius-pill)",
                padding: "10px 18px",
                fontSize: "13px",
                outline: "none",
              }}
            />
            <button
              onClick={() => handleSend()}
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "50%",
                background: "#000000",
                color: "#ffffff",
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
              }}
            >
              <ArrowUp size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
