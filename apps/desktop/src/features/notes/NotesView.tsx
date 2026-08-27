import React, { useState, useEffect, useRef, useCallback } from "react";
import { Note } from "../../types";
import { notesApi } from "../../services/api/notes";
import { detectIntentsInNote } from "../notepad/intentParser";
import { intentRouter } from "../notepad/router";
import { notepadApi } from "../../services/api/notepad";
import type { Intent } from "../notepad/types";
import { IntentSurface } from "../notepad/components/IntentSurface";
import { AtAutocomplete } from "../notepad/components/AtAutocomplete";

export const NotesView: React.FC = () => {
  const [activeNote, setActiveNote] = useState<Note | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [currentTime, setCurrentTime] = useState("");
  const [currentDate, setCurrentDate] = useState("");
  const [intents, setIntents] = useState<Intent[]>([]);
  const [atOpen, setAtOpen] = useState(false);
  const [atFilter, setAtFilter] = useState("");
  const [atPos, setAtPos] = useState<{ top: number; left: number } | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    loadNotes();
    updateClock();
    const timer = setInterval(updateClock, 60000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    return intentRouter.subscribe((updated) => {
      setIntents((prev) => {
        const idx = prev.findIndex((p) => p.id === updated.id);
        if (idx === -1) return [...prev, updated];
        const next = [...prev];
        next[idx] = updated;
        return next;
      });
    });
  }, []);

  // Persist intents whenever the in-memory list changes and we have an
  // active note. Best-effort: failure must never block the UI.
  useEffect(() => {
    if (!activeNote) return;
    // Avoid saving on the very first hydration (no real change yet).
    if (intents.length === 0) return;
    notepadApi
      .saveIntents(activeNote.id, intents)
      .catch((e) => console.warn("Intent sidecar save failed:", e));
  }, [intents, activeNote]);

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
      // Always set the current note text on the router BEFORE detection so
      // the router can build bounded context for any subsequent route call.
      intentRouter.setCurrentNoteText(detail.content);
      // Slice 1.1: prefer persisted intents from the sidecar; fall back to
      // local detection if the sidecar is missing or malformed.
      let nextIntents: Intent[] = [];
      try {
        const loaded = await notepadApi.loadIntents(detail.id);
        if (loaded.malformed) {
          // Warn but do not block — local detection still runs.
          console.warn("Notepad intents sidecar was malformed; using local detection.");
        }
        if (loaded.intents && loaded.intents.length > 0) {
          nextIntents = loaded.intents;
        } else {
          nextIntents = detectIntentsInNote(detail.content, detail.id);
        }
      } catch (e) {
        // If the persistence endpoint is unreachable, fall back to detection.
        nextIntents = detectIntentsInNote(detail.content, detail.id);
      }
      intentRouter.replaceAll(nextIntents);
      setIntents(nextIntents);
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
      // Slice 1.1: persist the current intent set to the sidecar. We do
      // this after the note save so the SQLite row exists, and we do it
      // best-effort — failure here must NOT corrupt the note.
      if (activeNote) {
        try {
          await notepadApi.saveIntents(activeNote.id, intents);
        } catch (e) {
          console.warn("Failed to persist intent sidecar:", e);
        }
      }
      loadNotes();
    } catch (e) {
      console.error("Failed to save note", e);
    }
  };

  // --- Notepad: intent detection runs on every content change. The plain
  //     note save/load path is unchanged; intents only populate the in-memory
  //     IntentRouter and render below the editor. The note file on disk is
  //     never modified by detection.
  const handleContentChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const next = e.target.value;
    setContent(next);
    // Always keep the router in sync with the current note text so that
    // a subsequent @ai route call can build a bounded, accurate context.
    intentRouter.setCurrentNoteText(next);
    if (activeNote) {
      const detected = detectIntentsInNote(next, activeNote.id);
      intentRouter.replaceAll(detected);
      setIntents(detected);
    }
  }, [activeNote]);

  // --- Notepad: @ autocomplete opens on '@' and dismisses on Escape.
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "@") {
        // Position popover near caret.
        const ta = textareaRef.current;
        if (ta) {
          const rect = ta.getBoundingClientRect();
          setAtPos({ top: rect.top + 24, left: rect.left + 12 });
        }
        setAtFilter("");
        setAtOpen(true);
        return;
      }
      if (atOpen) {
        if (e.key === "Escape") {
          setAtOpen(false);
          e.preventDefault();
        }
        return;
      }
      // Cmd-Enter (or Ctrl-Enter) routes the first detected AI intent.
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        const first = intents.find(
          (i) => i.capability_id === "ai" && i.status === "DETECTED"
        );
        if (first) {
          e.preventDefault();
          intentRouter.route(first.id).catch((err) => {
            console.error("Route failed", err);
          });
        }
      }
    },
    [atOpen, intents]
  );

  const handleAtSelect = useCallback(
    (capabilityId: string) => {
      const ta = textareaRef.current;
      if (!ta) return;
      const insert = `@${capabilityId} `;
      const start = ta.selectionStart ?? content.length;
      const end = ta.selectionEnd ?? content.length;
      // Find the '@' we triggered on and replace from there.
      const before = content.slice(0, start);
      const atIdx = before.lastIndexOf("@");
      const safeStart = atIdx >= 0 ? atIdx : start;
      const next = content.slice(0, safeStart) + insert + content.slice(end);
      setContent(next);
      setAtOpen(false);
      if (activeNote) {
        const detected = detectIntentsInNote(next, activeNote.id);
        intentRouter.replaceAll(detected);
        setIntents(detected);
      }
      // Refocus and place caret after the inserted text.
      setTimeout(() => {
        ta.focus();
        const caret = safeStart + insert.length;
        ta.setSelectionRange(caret, caret);
      }, 0);
    },
    [content, activeNote]
  );

  const handleRoute = useCallback((id: string) => {
    intentRouter.route(id).catch((err) => console.error("Route failed", err));
  }, []);

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
        ref={textareaRef}
        value={content}
        onChange={handleContentChange}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        placeholder="Lets do work dude..."
        data-testid="notepad-textarea"
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

      {/* Notepad Intent Surface (NEW, Slice 1). Renders below the editor and
          does NOT alter the editor's appearance, the save/load path, or any
          other Notepad behavior. */}
      <IntentSurface
        intents={intents}
        onRoute={handleRoute}
        onApprove={(id) => console.log("approve (slice 1: not used):", id)}
        onReject={(id) => console.log("reject (slice 1: not used):", id)}
      />

      <AtAutocomplete
        open={atOpen}
        filter={atFilter}
        position={atPos}
        onSelect={handleAtSelect}
        onDismiss={() => setAtOpen(false)}
      />
    </div>
  );
};
