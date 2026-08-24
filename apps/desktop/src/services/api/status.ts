import { apiRequest } from "./client";
import { SystemStatus } from "../../types";

export const statusApi = {
  get: (): Promise<SystemStatus> => apiRequest<SystemStatus>("/status"),
};
