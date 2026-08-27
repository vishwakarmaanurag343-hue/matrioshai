import React, { useEffect, useRef } from "react";
import { CAPABILITIES } from "../capabilities";

interface AtAutocompleteProps {
  open: boolean;
  filter: string;
  position: { top: number; left: number } | null;
  onSelect: (capabilityId: string) => void;
  onDismiss: () => void;
}

/**
 * @-autocomplete popover. Shows the two registered capabilities in slice 1.
 * Disabled capabilities (e.g. browser) are visible but clearly marked and
 * cannot be selected into the editor.
 */
export const AtAutocomplete: React.FC<AtAutocompleteProps> = ({
  open,
  filter,
  position,
  onSelect,
  onDismiss,
}) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onDismiss();
      }
    };
    window.addEventListener("mousedown", handler);
    return () => window.removeEventListener("mousedown", handler);
  }, [open, onDismiss]);

  if (!open || !position) return null;

  const filterLower = filter.toLowerCase();
  const entries = Object.values(CAPABILITIES).filter((c) =>
    filterLower.length === 0 ? true : c.id.startsWith(filterLower)
  );

  return (
    <div
      ref={ref}
      data-testid="at-autocomplete"
      style={{
        position: "fixed",
        top: position.top,
        left: position.left,
        zIndex: 1000,
        background: "var(--bg-card)",
        border: "1px solid rgba(0,0,0,0.08)",
        borderRadius: 8,
        boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
        minWidth: 220,
        padding: 6,
        fontSize: 13,
      }}
    >
      {entries.length === 0 && (
        <div style={{ padding: "8px 10px", color: "var(--text-muted)" }}>No capability matches.</div>
      )}
      {entries.map((c) => {
        const disabled = !c.enabled;
        return (
          <button
            key={c.id}
            type="button"
            disabled={disabled}
            onClick={() => {
              if (!disabled) onSelect(c.id);
            }}
            data-testid={`at-option-${c.id}`}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "8px 10px",
              border: "none",
              background: disabled ? "transparent" : "transparent",
              color: disabled ? "var(--text-muted)" : "var(--text-primary)",
              cursor: disabled ? "not-allowed" : "pointer",
              borderRadius: 6,
              opacity: disabled ? 0.6 : 1,
            }}
          >
            <div style={{ fontWeight: 600 }}>@{c.id}</div>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
              {c.name} —{" "}
              {disabled
                ? c.deferralMessage ?? "not enabled in this phase"
                : c.supportedActions.join(", ")}
            </div>
          </button>
        );
      })}
    </div>
  );
};
