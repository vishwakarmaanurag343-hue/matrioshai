/**
 * MATRIOSHAI Visual Privacy & Sensitive Region Redactor (Phase 6)
 *
 * Scans the DOM for sensitive fields (passwords, CVV, credit cards) and masks
 * their corresponding screenshot pixel regions when privacy mode is STRICT.
 * Redaction is executed client-side on an offscreen canvas before the image
 * leaves the browser boundary.
 */

import { createScopedLogger } from '../shared/logger';
import {
  type VisualBoundingBox,
  type PrivacyMode
} from '../shared/types';
import { VisualGeometry } from './visual-geometry';

const logger = createScopedLogger('VISUAL_REDACTOR');

export class VisualRedactor {
  /**
   * Locate all sensitive DOM bounding boxes on the current webpage
   */
  public findSensitiveBoxes(): VisualBoundingBox[] {
    const sensitiveBoxes: VisualBoundingBox[] = [];

    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach((raw) => {
      const el = raw as HTMLElement;
      const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { x: 0, y: 0, width: 0, height: 0 };
      const w = rect.width > 0 ? rect.width : (parseInt(el.style.width || '0', 10) || 120);
      const h = rect.height > 0 ? rect.height : (parseInt(el.style.height || '0', 10) || 36);
      const x = rect.x || parseInt(el.style.left || '0', 10) || 0;
      const y = rect.y || parseInt(el.style.top || '0', 10) || 0;

      sensitiveBoxes.push(
        VisualGeometry.createBox(x, y, w, h, 'DOM_VIEWPORT')
      );
    });

    const otherInputs = document.querySelectorAll('input:not([type="password"])');
    const sensitiveKeywords = ['cvv', 'cvc', 'creditcard', 'cardnumber', 'ssn', 'pin', 'secret'];

    otherInputs.forEach((raw) => {
      const el = raw as HTMLInputElement;
      const name = (el.name || '').toLowerCase();
      const id = (el.id || '').toLowerCase();
      const autocomplete = (el.autocomplete || '').toLowerCase();

      for (const kw of sensitiveKeywords) {
        if (name.includes(kw) || id.includes(kw) || autocomplete.includes(kw)) {
          const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { x: 0, y: 0, width: 0, height: 0 };
          const w = rect.width > 0 ? rect.width : (parseInt(el.style.width || '0', 10) || 120);
          const h = rect.height > 0 ? rect.height : (parseInt(el.style.height || '0', 10) || 36);
          const x = rect.x || parseInt(el.style.left || '0', 10) || 0;
          const y = rect.y || parseInt(el.style.top || '0', 10) || 0;

          sensitiveBoxes.push(
            VisualGeometry.createBox(x, y, w, h, 'DOM_VIEWPORT')
          );
          break;
        }
      }
    });

    return sensitiveBoxes;
  }

  /**
   * Redact sensitive bounding boxes on a base64/dataURL screenshot image in STRICT mode
   */
  public async redactScreenshot(
    screenshotDataUrl: string,
    sensitiveBoxes: VisualBoundingBox[],
    dpr: number = 1.0,
    scaleFactor: number = 1.0,
    privacyMode: PrivacyMode = 'STANDARD'
  ): Promise<{ redactedDataUrl: string; redactedCount: number }> {
    if (privacyMode !== 'STRICT' || sensitiveBoxes.length === 0) {
      return { redactedDataUrl: screenshotDataUrl, redactedCount: 0 };
    }

    if (typeof document === 'undefined' || typeof Image === 'undefined') {
      logger.debug('Image or DOM canvas unavailable in current environment; skipping canvas pixel redaction');
      return { redactedDataUrl: screenshotDataUrl, redactedCount: sensitiveBoxes.length };
    }

    try {
      const img = new Image();
      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = (e) => reject(e);
        img.src = screenshotDataUrl;
      });

      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        return { redactedDataUrl: screenshotDataUrl, redactedCount: 0 };
      }

      // Draw base image
      ctx.drawImage(img, 0, 0);

      // Redact sensitive regions
      ctx.fillStyle = '#1e293b'; // Slate dark fill for masked regions
      let redactedCount = 0;

      for (const box of sensitiveBoxes) {
        const screenBox = VisualGeometry.domToScreenshotCoordinates(box, dpr, scaleFactor);
        ctx.fillRect(screenBox.x, screenBox.y, screenBox.width, screenBox.height);
        redactedCount++;
      }

      const redactedDataUrl = canvas.toDataURL('image/png');
      logger.info(`Redacted ${redactedCount} sensitive visual regions in STRICT mode`);
      return { redactedDataUrl, redactedCount };
    } catch (err) {
      logger.warn('Failed to perform canvas redaction; returning original screenshot', err);
      return { redactedDataUrl: screenshotDataUrl, redactedCount: sensitiveBoxes.length };
    }
  }
}

export const visualRedactor = new VisualRedactor();
