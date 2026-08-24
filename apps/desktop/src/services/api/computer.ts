import { apiRequest } from "./client";
import {
  ComputerStatus,
  ScreenshotCapture,
  VisionAnalysis,
  ApplicationContext
} from "../../types";

export const computerApi = {
  getStatus: (): Promise<ComputerStatus> =>
    apiRequest<ComputerStatus>("/computer/status"),

  emergencyStop: (): Promise<ComputerStatus> =>
    apiRequest<ComputerStatus>("/computer/emergency-stop", {
      method: "POST",
    }),

  startSession: (taskId?: string): Promise<any> =>
    apiRequest<any>(taskId ? `/computer/session/start?task_id=${taskId}` : "/computer/session/start", {
      method: "POST",
    }),

  stopSession: (): Promise<any> =>
    apiRequest<any>("/computer/session/stop", {
      method: "POST",
    }),

  captureScreenshot: (): Promise<ScreenshotCapture> =>
    apiRequest<ScreenshotCapture>("/computer/screenshot", {
      method: "POST",
    }),

  analyzeScreen: (screenshot: ScreenshotCapture): Promise<VisionAnalysis> =>
    apiRequest<VisionAnalysis>("/computer/analyze", {
      method: "POST",
      body: JSON.stringify(screenshot),
    }),

  getActiveApplication: (): Promise<ApplicationContext> =>
    apiRequest<ApplicationContext>("/computer/application"),
};
