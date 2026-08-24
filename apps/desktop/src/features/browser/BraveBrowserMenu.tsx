import React from "react";
import {
  Plus,
  Square,
  Lock,
  Key,
  History as HistoryIcon,
  Bookmark,
  Download,
  Trash2,
  Printer,
  Settings,
  ChevronRight,
  Shield,
  User,
} from "lucide-react";

interface BraveBrowserMenuProps {
  isOpen: boolean;
  onClose: () => void;
  onNewTab: () => void;
  onNewPrivateWindow: () => void;
  onOpenPasswords: () => void;
  onOpenHistory: () => void;
  onOpenBookmarks: () => void;
  onOpenDownloads: () => void;
  onOpenShields: () => void;
  onOpenProfiles: () => void;
  onOpenSettings: () => void;
  onZoom: (delta: number) => void;
  onResetZoom: () => void;
  zoomLevel: number;
  onPrint: () => void;
  onClearHistory: () => void;
}

export const BraveBrowserMenu: React.FC<BraveBrowserMenuProps> = ({
  isOpen,
  onClose,
  onNewTab,
  onNewPrivateWindow,
  onOpenPasswords,
  onOpenHistory,
  onOpenBookmarks,
  onOpenDownloads,
  onOpenShields,
  onOpenProfiles,
  onOpenSettings,
  onZoom,
  onResetZoom,
  zoomLevel,
  onPrint,
  onClearHistory,
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "absolute",
        top: "78px",
        right: "24px",
        width: "280px",
        background: "#18181b",
        color: "#f4f4f5",
        borderRadius: "14px",
        boxShadow: "0 16px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.08)",
        zIndex: 99999,
        padding: "6px 0",
        fontSize: "12px",
        userSelect: "none",
        backdropFilter: "blur(20px)",
      }}
    >
      {/* Group 1: New Tab / Windows */}
      <div style={{ padding: "4px 0", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <div
          onClick={() => {
            onNewTab();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Plus size={14} />
            <span>New Tab</span>
          </div>
          <span style={{ color: "#71717a", fontSize: "11px" }}>⌘T</span>
        </div>

        <div
          onClick={() => {
            onNewTab();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Square size={14} />
            <span>New Window</span>
          </div>
          <span style={{ color: "#71717a", fontSize: "11px" }}>⌘N</span>
        </div>

        <div
          onClick={() => {
            onNewPrivateWindow();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Lock size={14} />
            <span>New Private Window</span>
          </div>
          <span style={{ color: "#71717a", fontSize: "11px" }}>⇧⌘N</span>
        </div>
      </div>

      {/* Group 2: Matrioshai AI / Shields */}
      <div style={{ padding: "4px 0", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <div
          onClick={() => {
            onOpenShields();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Shield size={14} color="#10b981" />
            <span>Matrioshai Shields</span>
          </div>
        </div>

        <div
          onClick={() => {
            onOpenProfiles();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <User size={14} color="#3b82f6" />
            <span>Profiles & Containers</span>
          </div>
        </div>
      </div>

      {/* Group 3: Core Browser Tools */}
      <div style={{ padding: "4px 0", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <div
          onClick={() => {
            onOpenPasswords();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Key size={14} />
            <span>Passwords and autofill</span>
          </div>
          <ChevronRight size={12} color="#71717a" />
        </div>

        <div
          onClick={() => {
            onOpenHistory();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <HistoryIcon size={14} />
            <span>History</span>
          </div>
          <ChevronRight size={12} color="#71717a" />
        </div>

        <div
          onClick={() => {
            onOpenBookmarks();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Bookmark size={14} />
            <span>Bookmarks and lists</span>
          </div>
          <ChevronRight size={12} color="#71717a" />
        </div>

        <div
          onClick={() => {
            onOpenDownloads();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Download size={14} />
            <span>Downloads</span>
          </div>
          <span style={{ color: "#71717a", fontSize: "11px" }}>⌥⌘L</span>
        </div>

        <div
          onClick={() => {
            onClearHistory();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Trash2 size={14} color="#ef4444" />
            <span>Delete Browsing Data...</span>
          </div>
          <span style={{ color: "#71717a", fontSize: "11px" }}>⇧⌘⌫</span>
        </div>
      </div>

      {/* Group 4: Zoom Controls */}
      <div
        style={{
          padding: "6px 14px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <span style={{ fontWeight: 500 }}>Zoom</span>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            background: "#27272a",
            borderRadius: "8px",
            padding: "2px 6px",
            gap: "8px",
          }}
        >
          <button
            onClick={() => onZoom(-0.1)}
            style={{ background: "transparent", border: "none", color: "#f4f4f5", cursor: "pointer", padding: "2px 4px" }}
          >
            -
          </button>
          <span
            onClick={onResetZoom}
            style={{ fontSize: "11px", fontWeight: 700, minWidth: "36px", textAlign: "center", cursor: "pointer" }}
          >
            {Math.round(zoomLevel * 100)}%
          </span>
          <button
            onClick={() => onZoom(0.1)}
            style={{ background: "transparent", border: "none", color: "#f4f4f5", cursor: "pointer", padding: "2px 4px" }}
          >
            +
          </button>
        </div>
      </div>

      {/* Group 5: Print & Settings */}
      <div style={{ padding: "4px 0" }}>
        <div
          onClick={() => {
            onPrint();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Printer size={14} />
            <span>Print...</span>
          </div>
          <span style={{ color: "#71717a", fontSize: "11px" }}>⌘P</span>
        </div>

        <div
          onClick={() => {
            onOpenSettings();
            onClose();
          }}
          className="brave-menu-item"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Settings size={14} />
            <span>Settings</span>
          </div>
        </div>
      </div>

      <style>{`
        .brave-menu-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 14px;
          cursor: pointer;
          transition: background 0.15s ease;
        }
        .brave-menu-item:hover {
          background: #27272a;
        }
      `}</style>
    </div>
  );
};
