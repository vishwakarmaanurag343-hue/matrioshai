/**
 * MATRIOSHAI Visual Query Engine (Phase 6)
 *
 * Implements deterministic visual queries over the VisualPageModel:
 * - Point queries: findVisualElementsAtPoint(x, y) with z-index candidate ordering
 * - Region queries: findVisualElementsInRegion(regionId)
 * - Type queries: findVisualElementsByType(type)
 * - Semantic correspondence: findVisualElementForSemanticElement(elementId)
 * - Geometric intersection queries: contains, intersects, nearest
 */

import {
  type VisualPageModel,
  type VisualElement,
  type VisualQuery,
  type VisualQueryResult,
  type PointQueryResult,
  type VisualBoundingBox,
  type CoordinateSystem
} from '../shared/types';
import { VisualGeometry } from './visual-geometry';

export class VisualQueryEngine {
  /**
   * Deterministic point query locating visual elements at screen/DOM coordinates (x, y).
   * Sorts candidates by z_index descending to determine the topmost element.
   */
  public queryPoint(
    model: VisualPageModel,
    x: number,
    y: number,
    coordinateSystem: CoordinateSystem = 'DOM_VIEWPORT'
  ): PointQueryResult {
    if (model.is_stale) {
      return {
        status: 'STALE',
        x,
        y,
        coordinate_system: coordinateSystem,
        candidates: [],
        message: 'Visual page model is stale. A fresh observation is required.'
      };
    }

    // Normalize point to DOM_VIEWPORT coordinates if given in SCREENSHOT_PIXEL
    let domX = x;
    let domY = y;
    if (coordinateSystem === 'SCREENSHOT_PIXEL') {
      const dpr = model.screenshot.device_pixel_ratio || 1.0;
      const scale = model.screenshot.scaled ? model.screenshot.width / model.screenshot.original_width : 1.0;
      const domBox = VisualGeometry.screenshotToDomCoordinates(
        VisualGeometry.createBox(x, y, 1, 1, 'SCREENSHOT_PIXEL'),
        dpr,
        scale
      );
      domX = domBox.x;
      domY = domBox.y;
    }

    const matchingElements = model.visual_elements.filter((el) =>
      VisualGeometry.containsPoint(el.dom_box, domX, domY)
    );

    if (matchingElements.length === 0) {
      return {
        status: 'NOT_FOUND',
        x,
        y,
        coordinate_system: coordinateSystem,
        candidates: [],
        message: `No visual element found at coordinates (${x}, ${y}).`
      };
    }

    // Sort matching elements by z_index descending (topmost on top)
    matchingElements.sort((a, b) => b.z_index - a.z_index);

    const candidates = matchingElements.map((el, idx) => {
      const isOccluded = idx > 0; // Any element beneath index 0 is at least partially occluded at this point
      return {
        element: el,
        z_index: el.z_index,
        occluded: isOccluded,
        confidence: el.confidence
      };
    });

    const topmost = matchingElements[0];

    // Ambiguity check: if multiple elements share exact highest z-index and are distinct
    const highestZ = topmost.z_index;
    const sameZMatches = matchingElements.filter((m) => m.z_index === highestZ);
    const status = sameZMatches.length > 1 ? 'AMBIGUOUS' : 'FOUND';

    return {
      status,
      x,
      y,
      coordinate_system: coordinateSystem,
      topmost_element: topmost,
      candidates,
      message:
        status === 'AMBIGUOUS'
          ? `Multiple (${sameZMatches.length}) elements share identical z-order at (${x}, ${y}).`
          : `Located topmost visual element [${topmost.visual_id}] (${topmost.type}) at (${x}, ${y}).`
    };
  }

  /**
   * Query visual elements matching structured criteria
   */
  public query(model: VisualPageModel, querySpec: VisualQuery): VisualQueryResult {
    if (model.is_stale) {
      return {
        status: 'STALE',
        elements: [],
        mappings: [],
        count: 0,
        query: querySpec,
        message: 'Visual page model is stale.'
      };
    }

    let results = [...model.visual_elements];

    if (querySpec.type) {
      const t = querySpec.type.toUpperCase();
      results = results.filter((el) => el.type === t);
    }

    if (querySpec.region_id) {
      const region = model.regions.find((r) => r.region_id === querySpec.region_id);
      if (region) {
        const idSet = new Set(region.visual_element_ids);
        results = results.filter((el) => idSet.has(el.visual_id));
      } else {
        results = [];
      }
    }

    if (querySpec.semantic_element_id) {
      results = results.filter((el) => el.semantic_element_id === querySpec.semantic_element_id);
    }

    if (querySpec.interactive_only) {
      results = results.filter((el) => el.is_interactive);
    }

    if (querySpec.visible_only) {
      results = results.filter((el) => el.visibility === 'fully_visible' || el.visibility === 'partially_visible');
    }

    const matchedVisualIds = new Set(results.map((r) => r.visual_id));
    const matchingMappings = model.mappings.filter((m) => matchedVisualIds.has(m.visual_id));

    if (results.length === 0) {
      return {
        status: 'NOT_FOUND',
        elements: [],
        mappings: [],
        count: 0,
        query: querySpec,
        message: 'No visual elements matched the query criteria.'
      };
    }

    return {
      status: results.length === 1 ? 'FOUND' : 'FOUND',
      elements: results,
      mappings: matchingMappings,
      count: results.length,
      query: querySpec,
      message: `Found ${results.length} matching visual elements.`
    };
  }

  /**
   * Find elements intersecting a given rectangle
   */
  public findIntersecting(model: VisualPageModel, targetRect: VisualBoundingBox): VisualElement[] {
    return model.visual_elements.filter((el) => VisualGeometry.intersectsRect(el.dom_box, targetRect));
  }
}

export const visualQueryEngine = new VisualQueryEngine();
