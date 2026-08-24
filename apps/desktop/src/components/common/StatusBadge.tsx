import React, { useEffect, useState } from "react";
import { statusApi } from "../../services/api/status";
import { SystemStatus } from "../../types";

export const StatusBadge: React.FC = () => {
  const [statusData, setStatusData] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchStatus = async () => {
    try {
      const data = await statusApi.get();
      setStatusData(data);
    } catch {
      setStatusData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="status-pill">
        <span className="status-dot unavailable"></span>
        <span>LOCAL AI: Checking...</span>
      </div>
    );
  }

  const isOllamaConnected = statusData?.ollama?.status === "Connected";
  const isModelLoaded = statusData?.model?.status === "Loaded";
  const isOk = isOllamaConnected && isModelLoaded;

  return (
    <div className="status-pill" title={statusData?.ollama?.details || "Status"}>
      <span className={`status-dot ${isOk ? "connected" : "unavailable"}`}></span>
      <span>
        LOCAL AI: {isOk ? "Connected" : isOllamaConnected ? "Missing Model" : "Unavailable"}
      </span>
    </div>
  );
};
