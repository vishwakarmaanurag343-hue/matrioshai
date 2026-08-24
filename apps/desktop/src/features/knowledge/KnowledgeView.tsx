import React, { useState, useEffect } from "react";
import { Network, Search, Layers } from "lucide-react";
import { knowledgeApi, GraphEntity, GraphRelationship } from "../../services/api/knowledge_proactive";

export const KnowledgeView: React.FC = () => {
  const [entities, setEntities] = useState<GraphEntity[]>([]);
  const [relationships, setRelationships] = useState<GraphRelationship[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedEntity, setSelectedEntity] = useState<GraphEntity | null>(null);

  useEffect(() => {
    loadGraph();
  }, []);

  const loadGraph = async () => {
    try {
      const g = await knowledgeApi.getGraph();
      setEntities(g.entities);
      setRelationships(g.relationships);
      if (g.entities.length > 0 && !selectedEntity) {
        setSelectedEntity(g.entities[0]);
      }
    } catch (e) {
      // transient load error
    }
  };

  const filteredEntities = entities.filter((e) =>
    e.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    e.entity_type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Network size={20} color="var(--accent-primary)" />
          <h2 style={{ fontSize: "16px", fontWeight: 700 }}>Personal Knowledge Graph & Entity Relationships</h2>
        </div>
        <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
          Nodes: <strong>{entities.length}</strong> | Edges: <strong>{relationships.length}</strong>
        </div>
      </div>

      {/* 2-Pane Split: Left (Entities List) | Right (Graph Details & Relationships) */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Left: Entity Explorer */}
        <div style={{ width: "320px", borderRight: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", flexDirection: "column" }}>
          <div style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", background: "var(--bg-tertiary)", padding: "6px 10px", borderRadius: "6px" }}>
              <Search size={14} color="var(--text-muted)" />
              <input
                type="text"
                placeholder="Search entities & types..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ background: "transparent", border: "none", color: "var(--text-primary)", fontSize: "12px", outline: "none", width: "100%" }}
              />
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
            {filteredEntities.map((ent) => (
              <div
                key={ent.id}
                onClick={() => setSelectedEntity(ent)}
                style={{
                  padding: "10px 12px",
                  borderRadius: "6px",
                  background: selectedEntity?.id === ent.id ? "var(--bg-tertiary)" : "transparent",
                  border: selectedEntity?.id === ent.id ? "1px solid var(--accent-primary)" : "1px solid transparent",
                  cursor: "pointer",
                  marginBottom: "4px"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: "12px" }}>{ent.name}</strong>
                  <span style={{ fontSize: "10px", padding: "1px 6px", borderRadius: "4px", background: "rgba(59, 130, 246, 0.15)", color: "var(--accent-primary)" }}>
                    {ent.entity_type}
                  </span>
                </div>
                {ent.aliases.length > 1 && (
                  <div style={{ fontSize: "10px", color: "var(--text-muted)", marginTop: "2px" }}>
                    Aliases: {ent.aliases.join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right: Graph Inspector & Relationship Links */}
        <div style={{ flex: 1, background: "var(--bg-primary)", padding: "20px", overflowY: "auto" }}>
          {selectedEntity ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "800px" }}>
              {/* Selected Node Details */}
              <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                  <div>
                    <h3 style={{ fontSize: "18px", fontWeight: 700 }}>{selectedEntity.name}</h3>
                    <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
                      Canonical: {selectedEntity.canonical_name} | Type: {selectedEntity.entity_type}
                    </div>
                  </div>
                  <span style={{ fontSize: "11px", padding: "2px 8px", borderRadius: "12px", background: "rgba(16, 185, 129, 0.15)", color: "var(--status-green)", fontWeight: 700 }}>
                    Confidence: {(selectedEntity.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Connected Relationships */}
              <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
                <h4 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                  <Layers size={16} color="var(--accent-primary)" /> Connected Relationships
                </h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {relationships
                    .filter((r) => r.source_entity_id === selectedEntity.id || r.target_entity_id === selectedEntity.id)
                    .map((rel) => {
                      const isSource = rel.source_entity_id === selectedEntity.id;
                      const otherEntityId = isSource ? rel.target_entity_id : rel.source_entity_id;
                      const otherEntity = entities.find((e) => e.id === otherEntityId);

                      return (
                        <div key={rel.id} style={{ background: "var(--bg-tertiary)", padding: "10px 14px", borderRadius: "6px", display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "12px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span><strong>{isSource ? selectedEntity.name : otherEntity?.name}</strong></span>
                            <span style={{ fontSize: "10px", padding: "2px 6px", borderRadius: "4px", background: "var(--bg-secondary)", color: "var(--accent-primary)", fontWeight: 700 }}>
                              --[{rel.relationship_type}]--&gt;
                            </span>
                            <span><strong>{isSource ? otherEntity?.name : selectedEntity.name}</strong></span>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: "13px" }}>Select an entity on the left to inspect its relationships.</div>
          )}
        </div>
      </div>
    </div>
  );
};
