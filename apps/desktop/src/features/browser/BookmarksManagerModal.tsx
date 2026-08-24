import React, { useState } from "react";
import { Bookmark, Search, Trash2, X } from "lucide-react";

export interface BookmarkItem {
  id: string;
  title: string;
  url: string;
  folder?: string;
  createdAt: number;
}

interface BookmarksManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  bookmarks: BookmarkItem[];
  onNavigate: (url: string) => void;
  onAddBookmark: (title: string, url: string, folder?: string) => void;
  onDeleteBookmark: (id: string) => void;
}

export const BookmarksManagerModal: React.FC<BookmarksManagerModalProps> = ({
  isOpen,
  onClose,
  bookmarks,
  onNavigate,
  onDeleteBookmark,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);

  if (!isOpen) return null;

  const folders = Array.from(new Set(bookmarks.map((b) => b.folder || "Unorganized")));

  const filtered = bookmarks.filter((b) => {
    const matchesSearch =
      b.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      b.url.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFolder = !selectedFolder || (b.folder || "Unorganized") === selectedFolder;
    return matchesSearch && matchesFolder;
  });

  return (
    <div
      style={{
        position: "absolute",
        top: "78px",
        left: "180px",
        width: "420px",
        background: "rgba(255, 255, 255, 0.95)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderRadius: "16px",
        boxShadow: "0 12px 36px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.08)",
        zIndex: 9999,
        padding: "16px",
        color: "var(--text-primary)",
        fontSize: "13px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: 700, fontSize: "14px" }}>
          <Bookmark size={15} color="#f59e0b" /> Bookmarks Manager
        </div>
        <button
          onClick={onClose}
          style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }}
        >
          <X size={16} />
        </button>
      </div>

      {/* Search & Folder Filters */}
      <div style={{ display: "flex", gap: "6px", marginBottom: "10px" }}>
        <div style={{ position: "relative", flex: 1 }}>
          <Search size={13} style={{ position: "absolute", left: "8px", top: "8px", color: "var(--text-muted)" }} />
          <input
            type="text"
            placeholder="Search bookmarks..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: "100%",
              padding: "6px 8px 6px 26px",
              borderRadius: "8px",
              border: "1px solid rgba(0,0,0,0.1)",
              fontSize: "12px",
            }}
          />
        </div>
      </div>

      {/* Folder Chips */}
      <div style={{ display: "flex", gap: "6px", overflowX: "auto", marginBottom: "10px", paddingBottom: "2px" }}>
        <div
          onClick={() => setSelectedFolder(null)}
          style={{
            padding: "4px 8px",
            borderRadius: "12px",
            fontSize: "11px",
            fontWeight: 600,
            cursor: "pointer",
            background: selectedFolder === null ? "var(--text-primary)" : "var(--bg-card-secondary)",
            color: selectedFolder === null ? "#fff" : "var(--text-primary)",
          }}
        >
          All
        </div>
        {folders.map((f) => (
          <div
            key={f}
            onClick={() => setSelectedFolder(f)}
            style={{
              padding: "4px 8px",
              borderRadius: "12px",
              fontSize: "11px",
              fontWeight: 600,
              cursor: "pointer",
              background: selectedFolder === f ? "var(--text-primary)" : "var(--bg-card-secondary)",
              color: selectedFolder === f ? "#fff" : "var(--text-primary)",
              whiteSpace: "nowrap",
            }}
          >
            {f}
          </div>
        ))}
      </div>

      {/* Bookmarks List */}
      <div style={{ maxHeight: "240px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "4px" }}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: "center", padding: "20px", color: "var(--text-muted)", fontSize: "12px" }}>
            No bookmarks saved yet.
          </div>
        ) : (
          filtered.map((b) => (
            <div
              key={b.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px",
                borderRadius: "8px",
                background: "var(--bg-card-secondary)",
              }}
            >
              <div
                onClick={() => {
                  onNavigate(b.url);
                  onClose();
                }}
                style={{ cursor: "pointer", flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}
              >
                <div style={{ fontWeight: 600, fontSize: "12px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {b.title || b.url}
                </div>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {b.url}
                </div>
              </div>
              <button
                onClick={() => onDeleteBookmark(b.id)}
                title="Delete Bookmark"
                style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: "4px" }}
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
