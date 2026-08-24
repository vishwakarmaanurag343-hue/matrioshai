import React, { useState, useEffect } from "react";
import { Note } from "../../types";
import { notesApi } from "../../services/api/notes";

export const NotesView: React.FC = () => {
  const [activeNote, setActiveNote] = useState<Note | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [currentTime, setCurrentTime] = useState("");
  const [currentDate, setCurrentDate] = useState("");

  useEffect(() => {
    loadNotes();
    updateClock();
    const timer = setInterval(updateClock, 60000);
    return () => clearInterval(timer);
  }, []);

  const updateClock = () => {
    const now = new Date();
    setCurrentTime(now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    setCurrentDate(now.toLocaleDateString([], { day: "numeric", month: "long", year: "numeric" }));
  };

  const loadNotes = async () => {
    try {
      const data = await notesApi.list();
      if (data.length > 0 && !activeNote) {
        handleSelectNote(data[0].id);
      }
    } catch (e) {
      console.error("Failed to load notes", e);
    }
  };

  const handleSelectNote = async (id: string) => {
    try {
      const detail = await notesApi.get(id);
      setActiveNote(detail);
      setTitle(detail.title);
      setContent(detail.content);
    } catch (e) {
      console.error("Failed to get note detail", e);
    }
  };

  const handleSave = async () => {
    if (!title.trim() && !content.trim()) return;
    try {
      if (activeNote) {
        await notesApi.update(activeNote.id, { title, content });
      } else {
        const created = await notesApi.create({ title: title || "Note Heading", content });
        setActiveNote(created);
      }
      loadNotes();
    } catch (e) {
      console.error("Failed to save note", e);
    }
  };

  return (
    <div style={{ flex: 1, height: "100%", display: "flex", flexDirection: "column", padding: "30px 40px", position: "relative" }}>
      {/* Top Header Row: Note Heading Pill & Date/Time */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "30px" }}>
        {/* Note Heading Pill */}
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={handleSave}
          placeholder="Note Heading"
          style={{
            background: "var(--bg-card-secondary)",
            border: "1px solid rgba(0, 0, 0, 0.05)",
            borderRadius: "var(--radius-pill)",
            padding: "8px 24px",
            fontSize: "13px",
            fontWeight: 600,
            color: "var(--text-secondary)",
            outline: "none",
            width: "280px",
          }}
        />

        {/* Live Date & Time on Top Right */}
        <div style={{ textAlign: "right", fontSize: "11px", color: "var(--text-muted)", lineHeight: "1.4" }}>
          <div>{currentTime || "10:00 am"}</div>
          <div>{currentDate || "22 july 2026"}</div>
        </div>
      </div>

      {/* Note Content Canvas */}
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onBlur={handleSave}
        placeholder="Lets do work dude..."
        style={{
          flex: 1,
          width: "100%",
          border: "none",
          outline: "none",
          resize: "none",
          fontSize: "14px",
          lineHeight: "1.7",
          color: "var(--text-primary)",
          background: "transparent",
        }}
      />
    </div>
  );
};
