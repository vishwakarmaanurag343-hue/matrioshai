import React from "react";
import type { NotepadAIResponse } from "../types";

interface ResultCardProps {
  result: NotepadAIResponse;
}

/**
 * Renders the AI result clearly separated from the user's note content.
 * The user must always be able to distinguish NOTE CONTENT from AI RESULT.
 */
export const ResultCard: React.FC<ResultCardProps> = ({ result }) => {
  return (
    <div
      data-testid="result-card"
      style={{
        marginTop: 6,
        padding: 12,
        background: "var(--bg-card-secondary)",
        borderLeft: "3px solid #2c7a4b",
        borderRadius: 6,
        fontSize: 13,
        lineHeight: 1.6,
      }}
    >
      <div
        style={{
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: 1.2,
          color: "var(--text-muted)",
          marginBottom: 6,
        }}
      >
        AI Result — model {result.model} via {result.provider}
      </div>
      <div data-testid="result-summary" style={{ whiteSpace: "pre-wrap" }}>
        {result.summary}
      </div>
      {result.suggestions && result.suggestions.length > 0 && (
        <ul style={{ marginTop: 8, paddingLeft: 18, color: "var(--text-secondary)" }}>
          {result.suggestions.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      )}
    </div>
  );
};
