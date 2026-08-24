import React, { useState, useEffect } from "react";
import {
  Monitor,
  Camera,
  Eye,
  StopCircle,
  Layers,
  Sparkles,
  Loader2
} from "lucide-react";
import { computerApi } from "../../services/api/computer";
import {
  ComputerStatus,
  ScreenshotCapture,
  VisionAnalysis,
  ApplicationContext
} from "../../types";

export const ComputerView: React.FC = () => {
  const [status, setStatus] = useState<ComputerStatus | null>(null);
  const [screenshot, setScreenshot] = useState<ScreenshotCapture | null>(null);
  const [analysis, setAnalysis] = useState<VisionAnalysis | null>(null);
  const [activeApp, setActiveApp] = useState<ApplicationContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const [st, app] = await Promise.all([
        computerApi.getStatus(),
        computerApi.getActiveApplication(),
      ]);
      setStatus(st);
      setActiveApp(app);
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleCaptureScreen = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const cap = await computerApi.captureScreenshot();
      setScreenshot(cap);
      const ana = await computerApi.analyzeScreen(cap);
      setAnalysis(ana);
      const app = await computerApi.getActiveApplication();
      setActiveApp(app);
    } catch (e: any) {
      setErrorMsg(`Screen capture error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleEmergencyStop = async () => {
    try {
      const st = await computerApi.emergencyStop();
      setStatus(st);
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Top Bar: Emergency Stop & Status */}
      <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Monitor size={20} color="var(--accent-primary)" />
          <h2 style={{ fontSize: "16px", fontWeight: 700 }}>Multimodal Intelligence & Computer Use</h2>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {status && (
            <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "flex", gap: "8px" }}>
              <span>Privacy Mode: <strong>{status.privacy_mode}</strong></span>
              <span>Screen Rec: <strong>{status.screen_recording_permission}</strong></span>
            </span>
          )}
          <button
            onClick={handleEmergencyStop}
            style={{ background: "var(--status-red)", color: "#fff", border: "none", padding: "6px 14px", borderRadius: "6px", fontSize: "12px", fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
          >
            <StopCircle size={14} /> STOP COMPUTER CONTROL
          </button>
        </div>
      </div>

      {errorMsg && (
        <div style={{ padding: "8px 16px", background: "rgba(239, 68, 68, 0.15)", color: "var(--status-red)", fontSize: "12px" }}>
          {errorMsg}
        </div>
      )}

      {/* Main 2-Pane Split: Left (Screen Preview) | Right (Active App & Elements) */}
      <div style={{ flex: 1, display: "flex", padding: "16px", gap: "16px", overflowY: "auto" }}>
        {/* Left Side: Screen Preview */}
        <div style={{ flex: 2, background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px", display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <h3 style={{ fontSize: "14px", fontWeight: 700, display: "flex", alignItems: "center", gap: "6px" }}>
              <Eye size={16} color="var(--accent-primary)" /> Live Screen Perception
            </h3>
            <button className="new-chat-btn" onClick={handleCaptureScreen} disabled={loading} style={{ fontSize: "12px", padding: "6px 12px", gap: "6px" }}>
              {loading ? <Loader2 className="spinning" size={13} /> : <Camera size={13} />} Capture & Analyze
            </button>
          </div>

          <div style={{ flex: 1, background: "var(--bg-tertiary)", border: "1px dashed var(--border-color)", borderRadius: "6px", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", minHeight: "360px", position: "relative" }}>
            {screenshot ? (
              <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <img
                  src={`data:image/jpeg;base64,${screenshot.base64_image}`}
                  alt="Screen capture"
                  style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain", borderRadius: "4px" }}
                />
              </div>
            ) : (
              <div style={{ color: "var(--text-muted)", fontSize: "13px" }}>
                Click "Capture & Analyze" to perceive active macOS display.
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Active Application & Detected Elements */}
        <div style={{ flex: 1.2, display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* Active App Card */}
          <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "14px" }}>
            <h3 style={{ fontSize: "13px", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
              <Layers size={14} color="var(--accent-primary)" /> Active macOS Application
            </h3>
            {activeApp ? (
              <div style={{ fontSize: "12px" }}>
                <div>Application: <strong>{activeApp.application}</strong></div>
                <div style={{ color: "var(--text-muted)", marginTop: "2px" }}>Window: {activeApp.window_title || "N/A"}</div>
              </div>
            ) : (
              <div style={{ color: "var(--text-muted)", fontSize: "12px" }}>No active application detected</div>
            )}
          </div>

          {/* Detected Elements Card */}
          <div style={{ flex: 1, background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "14px", overflowY: "auto" }}>
            <h3 style={{ fontSize: "13px", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
              <Sparkles size={14} color="var(--accent-primary)" /> Detected UI Elements ({analysis?.elements.length || 0})
            </h3>
            {analysis && analysis.elements.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {analysis.elements.map((el, i) => (
                  <div key={i} style={{ background: "var(--bg-tertiary)", padding: "8px 10px", borderRadius: "6px", fontSize: "11px" }}>
                    <strong>{el.label}</strong> ({el.type})
                    <div style={{ color: "var(--text-muted)" }}>Coordinates: ({el.x}, {el.y}) | Size: {el.width}x{el.height}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: "var(--text-muted)", fontSize: "12px" }}>
                No elements detected yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
