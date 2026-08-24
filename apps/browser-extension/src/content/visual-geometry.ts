/**
 * MATRIOSHAI Visual Geometry & Coordinate System Transformations (Phase 6)
 *
 * Implements deterministic mathematical coordinate conversions between:
 * - DOM_VIEWPORT: CSS pixels relative to current viewport [0..width, 0..height]
 * - SCREENSHOT_PIXEL: Physical image pixels (DPR and scale-adjusted)
 * - DOCUMENT_SPACE: CSS pixels relative to document top-left
 *
 * Also provides geometric operators for collision detection, containment,
 * partial visibility, and nearest distance calculations.
 */

import {
  type VisualBoundingBox,
  type CoordinateSystem,
  type VisibilityState
} from '../shared/types';

export class VisualGeometry {
  /**
   * Convert a DOM Viewport bounding box (CSS pixels) to Screenshot physical pixel coordinates.
   * @param domBox Bounding box in DOM viewport CSS pixels
   * @param dpr Device pixel ratio (e.g. 1, 1.25, 1.5, 2, 3)
   * @param scaleFactor Proportional downscale factor applied to the screenshot (default 1.0)
   */
  public static domToScreenshotCoordinates(
    domBox: VisualBoundingBox,
    dpr: number = 1.0,
    scaleFactor: number = 1.0
  ): VisualBoundingBox {
    const effectiveFactor = dpr * scaleFactor;
    const x = Math.round(domBox.x * effectiveFactor);
    const y = Math.round(domBox.y * effectiveFactor);
    const width = Math.round(domBox.width * effectiveFactor);
    const height = Math.round(domBox.height * effectiveFactor);

    return {
      x,
      y,
      width,
      height,
      top: y,
      left: x,
      right: x + width,
      bottom: y + height,
      coordinate_system: 'SCREENSHOT_PIXEL'
    };
  }

  /**
   * Convert a Screenshot physical pixel bounding box back to DOM Viewport CSS pixels.
   * @param screenBox Bounding box in screenshot physical pixels
   * @param dpr Device pixel ratio
   * @param scaleFactor Proportional downscale factor
   */
  public static screenshotToDomCoordinates(
    screenBox: VisualBoundingBox,
    dpr: number = 1.0,
    scaleFactor: number = 1.0
  ): VisualBoundingBox {
    const effectiveFactor = dpr * scaleFactor;
    const invFactor = effectiveFactor > 0 ? 1.0 / effectiveFactor : 1.0;

    const x = Math.round(screenBox.x * invFactor);
    const y = Math.round(screenBox.y * invFactor);
    const width = Math.round(screenBox.width * invFactor);
    const height = Math.round(screenBox.height * invFactor);

    return {
      x,
      y,
      width,
      height,
      top: y,
      left: x,
      right: x + width,
      bottom: y + height,
      coordinate_system: 'DOM_VIEWPORT'
    };
  }

  /**
   * Convert Document space coordinates to DOM Viewport space.
   */
  public static documentToViewportCoordinates(
    docBox: VisualBoundingBox,
    scrollX: number = 0,
    scrollY: number = 0
  ): VisualBoundingBox {
    const x = docBox.x - scrollX;
    const y = docBox.y - scrollY;

    return {
      x,
      y,
      width: docBox.width,
      height: docBox.height,
      top: y,
      left: x,
      right: x + docBox.width,
      bottom: y + docBox.height,
      coordinate_system: 'DOM_VIEWPORT'
    };
  }

  /**
   * Convert DOM Viewport space coordinates to Document space.
   */
  public static viewportToDocumentCoordinates(
    viewBox: VisualBoundingBox,
    scrollX: number = 0,
    scrollY: number = 0
  ): VisualBoundingBox {
    const x = viewBox.x + scrollX;
    const y = viewBox.y + scrollY;

    return {
      x,
      y,
      width: viewBox.width,
      height: viewBox.height,
      top: y,
      left: x,
      right: x + viewBox.width,
      bottom: y + viewBox.height,
      coordinate_system: 'DOCUMENT_SPACE'
    };
  }

  /**
   * Determine if a point (x, y) falls inside a VisualBoundingBox.
   */
  public static containsPoint(box: VisualBoundingBox, x: number, y: number): boolean {
    return x >= box.left && x <= box.right && y >= box.top && y <= box.bottom;
  }

  /**
   * Determine if two bounding boxes intersect.
   */
  public static intersectsRect(boxA: VisualBoundingBox, boxB: VisualBoundingBox): boolean {
    return !(
      boxA.right < boxB.left ||
      boxA.left > boxB.right ||
      boxA.bottom < boxB.top ||
      boxA.top > boxB.bottom
    );
  }

  /**
   * Determine if outerBox fully contains innerBox.
   */
  public static containsRect(outerBox: VisualBoundingBox, innerBox: VisualBoundingBox): boolean {
    return (
      innerBox.left >= outerBox.left &&
      innerBox.right <= outerBox.right &&
      innerBox.top >= outerBox.top &&
      innerBox.bottom <= outerBox.bottom
    );
  }

  /**
   * Calculate euclidean distance from point (x, y) to the nearest edge of a box.
   * Returns 0 if point is inside the box.
   */
  public static distanceToPoint(box: VisualBoundingBox, x: number, y: number): number {
    if (this.containsPoint(box, x, y)) return 0;

    const dx = Math.max(box.left - x, 0, x - box.right);
    const dy = Math.max(box.top - y, 0, y - box.bottom);
    return Math.sqrt(dx * dx + dy * dy);
  }

  /**
   * Determine visibility state against viewport boundaries [0..viewportWidth, 0..viewportHeight].
   */
  public static classifyVisibility(
    domBox: VisualBoundingBox,
    viewportWidth: number,
    viewportHeight: number
  ): VisibilityState {
    if (domBox.width <= 0 || domBox.height <= 0) {
      return 'hidden';
    }

    const isCompletelyOutside =
      domBox.right <= 0 ||
      domBox.left >= viewportWidth ||
      domBox.bottom <= 0 ||
      domBox.top >= viewportHeight;

    if (isCompletelyOutside) {
      return 'outside_viewport';
    }

    const isFullyInside =
      domBox.left >= 0 &&
      domBox.right <= viewportWidth &&
      domBox.top >= 0 &&
      domBox.bottom <= viewportHeight;

    if (isFullyInside) {
      return 'fully_visible';
    }

    return 'partially_visible';
  }

  /**
   * Helper to create a VisualBoundingBox from DOMRect or coordinates.
   */
  public static createBox(
    x: number,
    y: number,
    width: number,
    height: number,
    coordSystem: CoordinateSystem = 'DOM_VIEWPORT'
  ): VisualBoundingBox {
    const rx = Math.round(x);
    const ry = Math.round(y);
    const rw = Math.round(width);
    const rh = Math.round(height);

    return {
      x: rx,
      y: ry,
      width: rw,
      height: rh,
      top: ry,
      left: rx,
      right: rx + rw,
      bottom: ry + rh,
      coordinate_system: coordSystem
    };
  }
}
