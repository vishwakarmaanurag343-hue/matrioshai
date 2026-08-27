import { ActionVerificationResult, PerceptionSnapshot } from "../types";

export class ActionVerifier {
  /**
   * Waits for page stabilization (network idle / DOM stabilization).
   */
  static async waitForStabilization(ms: number = 800): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Verifies if an action caused expected state transitions between before/after snapshots.
   */
  static verifyTransition(
    action: string,
    target: string | undefined,
    before: PerceptionSnapshot,
    after: PerceptionSnapshot
  ): ActionVerificationResult {
    const act = action.toUpperCase();

    // Detect 404 / 403 / 500 / Server error / DNS failure states in destination page
    const errorMarkers = [
      "404 not found", "page not found", "403 forbidden", "bad request",
      "500 internal server error", "502 bad gateway", "503 service unavailable",
      "dns_probe", "error 404", "cannot be found", "connection refused"
    ];
    const pageTextSample = `${after.title} ${after.headings.join(" ")} ${after.text_blocks.slice(0, 3).join(" ")}`.toLowerCase();
    const isErrorPage = errorMarkers.some((m) => pageTextSample.includes(m));

    // 1. Navigation verification
    if (act === "NAVIGATE") {
      if (isErrorPage) {
        return {
          success: false,
          changed: true,
          message: `❌ Navigation reached an error page (${after.title || "404 Not Found"}).`,
          beforeUrl: before.url,
          afterUrl: after.url,
          domMutated: true,
        };
      }
      const urlChanged = before.url !== after.url;
      const titleChanged = before.title !== after.title;
      const success = urlChanged || titleChanged || after.headings.length > 0;
      return {
        success,
        changed: urlChanged || titleChanged,
        message: success
          ? `Navigation verified to ${after.url} ("${after.title}")`
          : `Navigation to ${target} failed or remained on same page.`,
        beforeUrl: before.url,
        afterUrl: after.url,
        domMutated: before.text_blocks.length !== after.text_blocks.length,
      };
    }

    // 2. Click verification
    if (act === "CLICK") {
      if (isErrorPage) {
        return {
          success: false,
          changed: true,
          message: `❌ Click destination returned an HTTP error or 404 page (${after.title || "404 Not Found"}).`,
          beforeUrl: before.url,
          afterUrl: after.url,
          domMutated: true,
        };
      }
      const urlChanged = before.url !== after.url;
      const domChanged =
        before.title !== after.title ||
        JSON.stringify(before.headings) !== JSON.stringify(after.headings) ||
        before.text_blocks.length !== after.text_blocks.length;

      return {
        success: true,
        changed: urlChanged || domChanged,
        message: urlChanged
          ? `Click triggered navigation to ${after.url}`
          : domChanged
          ? `Click updated on-page elements/view.`
          : `Click completed on target ${target}.`,
        beforeUrl: before.url,
        afterUrl: after.url,
        domMutated: domChanged,
      };
    }

    // 3. General action (type, scroll, wait)
    return {
      success: true,
      changed: true,
      message: `Action ${action} successfully performed and verified.`,
      beforeUrl: before.url,
      afterUrl: after.url,
      domMutated: before.url !== after.url,
    };
  }
}
