import React, { useState, useEffect } from "react";
import { Settings as SettingsIcon, Save, RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";
import { AppSettings, SystemStatus } from "../../types";
import { settingsApi } from "../../services/api/settings";
import { statusApi } from "../../services/api/status";

export const SettingsView: React.FC = () => {
  const [settingsData, setSettingsData] = useState<AppSettings | null>(null);
  const [statusData, setStatusData] = useState<SystemStatus | null>(null);

  const [ollamaBaseUrl, setOllamaBaseUrl] = useState<string>("");
  const [ollamaModel, setOllamaModel] = useState<string>("");
  const [claudeKeyInput, setClaudeKeyInput] = useState<string>("");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);

  const loadAll = async () => {
    try {
      const [st, sys] = await Promise.all([settingsApi.get(), statusApi.get()]);
      setSettingsData(st);
      setStatusData(sys);
      setOllamaBaseUrl(st.ollama_base_url);
      setOllamaModel(st.ollama_model);
    } catch (err: any) {
      setStatusMsg(`Error loading settings: ${err.message}`);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await settingsApi.update({
        ollama_base_url: ollamaBaseUrl,
        ollama_model: ollamaModel,
      });
      setSettingsData(updated);
      setStatusMsg("Configuration saved successfully.");
      const sys = await statusApi.get();
      setStatusData(sys);
    } catch (err: any) {
      setStatusMsg(`Failed to save settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "24px", overflowY: "auto", gap: "24px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <SettingsIcon size={24} style={{ color: "var(--accent-primary)" }} />
        <div>
          <h2 style={{ fontSize: "18px", fontWeight: 700 }}>SETTINGS & DIAGNOSTICS</h2>
          <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
            Centralized application settings, Ollama configuration, and subsystem diagnostics
          </p>
        </div>
      </div>

      {statusMsg && (
        <div style={{ padding: "8px 14px", background: "var(--accent-light)", borderRadius: "6px", color: "var(--accent-primary)", fontSize: "13px" }}>
          {statusMsg}
        </div>
      )}

      {/* OLLAMA & LOCAL AI CONFIG */}
      <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700 }}>LOCAL MODEL PROVIDER (OLLAMA)</h3>
          <button className="new-chat-btn" onClick={handleSave} disabled={saving}>
            <Save size={14} />
            Save Settings
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div>
            <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
              Ollama Base URL
            </label>
            <input
              type="text"
              value={ollamaBaseUrl}
              onChange={(e) => setOllamaBaseUrl(e.target.value)}
              style={{
                width: "100%",
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-color)",
                color: "var(--text-primary)",
                padding: "8px 12px",
                borderRadius: "6px",
                fontSize: "13px",
                outline: "none",
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
              Configured Model Name
            </label>
            <input
              type="text"
              value={ollamaModel}
              onChange={(e) => setOllamaModel(e.target.value)}
              style={{
                width: "100%",
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-color)",
                color: "var(--text-primary)",
                padding: "8px 12px",
                borderRadius: "6px",
                fontSize: "13px",
                outline: "none",
              }}
            />
            <span style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px", display: "block" }}>
              Default: deepseek-r1:8b. Pull model via terminal: <code>ollama pull {ollamaModel || 'deepseek-r1:8b'}</code>
            </span>
          </div>
        </div>
      </div>

      {/* CODING AGENTS — CLAUDE CODE CONFIG */}
      <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div>
            <h3 style={{ fontSize: "14px", fontWeight: 700 }}>CODING AGENTS — CLAUDE CODE</h3>
            <p style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
              Orchestrated via DeepSeek Harness • User-Provided Anthropic Credential
            </p>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              className="action-btn"
              onClick={async () => {
                try {
                  const res = await settingsApi.testClaudeCodeConnection();
                  setStatusMsg(res.message);
                  await loadAll();
                } catch (e: any) {
                  setStatusMsg(`Claude connection failed: ${e.message}`);
                }
              }}
            >
              Test Connection
            </button>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "12px", fontWeight: 600 }}>Status:</span>
            <span
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: settingsData?.claude_code_configured ? "var(--status-green)" : "var(--status-amber)",
              }}
            >
              {settingsData?.claude_code_configured ? "● Connected / Configured" : "○ Not Configured"}
            </span>
          </div>

          <div>
            <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
              Claude / Anthropic API Key (Encrypted in Secret Store)
            </label>
            <div style={{ display: "flex", gap: "8px" }}>
              <input
                type="password"
                placeholder={settingsData?.claude_code_configured ? "••••••••••••••••••••••••" : "sk-ant-api..."}
                onChange={(e) => setClaudeKeyInput(e.target.value)}
                style={{
                  flex: 1,
                  background: "var(--bg-tertiary)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-primary)",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  fontSize: "13px",
                  outline: "none",
                }}
              />
              <button
                className="new-chat-btn"
                onClick={async () => {
                  if (claudeKeyInput) {
                    await settingsApi.update({ claude_code_api_key: claudeKeyInput });
                    setStatusMsg("Claude API Key securely stored in Keychain.");
                    setClaudeKeyInput("");
                    await loadAll();
                  }
                }}
              >
                Save Key
              </button>
            </div>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px", display: "block" }}>
              Key is never stored in plaintext SQLite, logs, or prompts. Injected ephemerally into Claude Code sub-agent workspace during execution.
            </span>
          </div>
        </div>
      </div>

      {/* SUBSYSTEM STATUS DIAGNOSTICS */}
      <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700 }}>SYSTEM STATUS DIAGNOSTICS</h3>
          <button className="action-btn" onClick={loadAll} title="Refresh Status">
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        {statusData && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "12px" }}>
            {[
              statusData.backend,
              statusData.database,
              statusData.ollama,
              statusData.model,
              statusData.memory,
              statusData.notes,
            ].map((comp, idx) => {
              const isOk = comp.status === "Connected" || comp.status === "Ready" || comp.status === "Loaded";
              return (
                <div
                  key={idx}
                  style={{
                    background: "var(--bg-tertiary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "6px",
                    padding: "12px",
                    display: "flex",
                    gap: "10px",
                    alignItems: "flex-start",
                  }}
                >
                  {isOk ? (
                    <CheckCircle2 size={18} color="var(--status-green)" style={{ marginTop: "2px" }} />
                  ) : (
                    <AlertCircle size={18} color="var(--status-amber)" style={{ marginTop: "2px" }} />
                  )}
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "13px" }}>{comp.name}</div>
                    <div style={{ fontSize: "12px", color: isOk ? "var(--status-green)" : "var(--status-amber)", fontWeight: 600 }}>
                      {comp.status}
                    </div>
                    {comp.details && (
                      <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                        {comp.details}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* STORAGE PATHS */}
      {settingsData && (
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "12px" }}>ISOLATED LOCAL STORAGE PATHS</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
            <div><strong>Database Path:</strong> <code>{settingsData.database_path}</code></div>
            <div><strong>Notes Path:</strong> <code>{settingsData.notes_path}</code></div>
            <div><strong>Memory Index Path:</strong> <code>{settingsData.memory_path}</code></div>
          </div>
        </div>
      )}
    </div>
  );
};
