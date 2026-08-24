/**
 * MATRIOSHAI Visual Page Engine (Phase 6)
 *
 * Orchestrates DOM visual extraction, screenshot coordinate mapping, region grouping,
 * sensitive field redaction, and multi-key indexing into a comprehensive VisualPageModel.
 */

import {
  type VisualPageModel,
  type VisualPageIndexes,
  type ScreenshotMetadata,
  type PrivacyMode,
  type ViewportMetrics
} from '../shared/types';
import { pageObservationEngine } from './observation-engine';
import { semanticPageAnalyzer } from './semantic-analyzer';
import { visualExtractor } from './visual-extractor';
import { visualRedactor } from './visual-redactor';

export class VisualEngine {
  private currentVisualVersion = 1;
  private lastVisualModel: VisualPageModel | null = null;

  public getVisualVersion(): number {
    return this.currentVisualVersion;
  }

  public incrementVisualVersion(): void {
    this.currentVisualVersion++;
    if (this.lastVisualModel) {
      this.lastVisualModel.is_stale = true;
    }
  }

  public invalidateModel(): void {
    this.incrementVisualVersion();
    this.lastVisualModel = null;
  }

  public getLastModel(): VisualPageModel | null {
    return this.lastVisualModel;
  }

  /**
   * Build complete VisualPageModel for the current live webpage
   */
  public generateVisualModel(
    tabId: number = 0,
    screenshotMeta?: Partial<ScreenshotMetadata>,
    privacyMode: PrivacyMode = 'STANDARD'
  ): VisualPageModel {
    const visualModelId = `vis_mod_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const observation = pageObservationEngine.extractPageObservation(tabId);
    let semanticModel = semanticPageAnalyzer.getLastModel();
    if (!semanticModel || semanticModel.is_stale) {
      semanticModel = semanticPageAnalyzer.analyzePage(tabId, observation.observation_id);
    }

    const dpr = typeof window !== 'undefined' && window.devicePixelRatio ? window.devicePixelRatio : 1.0;
    const viewport: ViewportMetrics = observation.viewport;

    const width = Math.round(viewport.width * dpr);
    const height = Math.round(viewport.height * dpr);

    const sensitiveBoxes = visualRedactor.findSensitiveBoxes();
    const redactedCount = privacyMode === 'STRICT' ? sensitiveBoxes.length : 0;

    const fullScreenshotMeta: ScreenshotMetadata = {
      id: screenshotMeta?.id || `screen_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      tab_id: tabId,
      url: window.location.href,
      width: screenshotMeta?.width || width,
      height: screenshotMeta?.height || height,
      device_pixel_ratio: dpr,
      scroll_x: viewport.scroll_x,
      scroll_y: viewport.scroll_y,
      timestamp: new Date().toISOString(),
      viewport_only: true,
      scaled: screenshotMeta?.scaled || false,
      original_width: screenshotMeta?.original_width || width,
      original_height: screenshotMeta?.original_height || height,
      format: screenshotMeta?.format || 'png',
      bytes: screenshotMeta?.bytes,
      privacy_mode: privacyMode,
      redacted_regions_count: redactedCount,
      observation_id: observation.observation_id,
      semantic_model_id: semanticModel.semantic_model_id,
      visual_version: this.currentVisualVersion
    };

    const scaleFactor = fullScreenshotMeta.scaled && fullScreenshotMeta.original_width > 0
      ? fullScreenshotMeta.width / fullScreenshotMeta.original_width
      : 1.0;

    const {
      visualElements,
      regions,
      overlays,
      fixedElements,
      stickyElements,
      mappings
    } = visualExtractor.extractVisuals(viewport, semanticModel.interactive_elements, dpr, scaleFactor);

    const indexes = this.buildIndexes(visualElements, regions);

    const model: VisualPageModel = {
      visual_model_id: visualModelId,
      visual_version: this.currentVisualVersion,
      observation_id: observation.observation_id,
      semantic_model_id: semanticModel.semantic_model_id,
      tab_id: tabId,
      is_stale: false,
      timestamp: new Date().toISOString(),
      screenshot: fullScreenshotMeta,
      viewport,
      regions,
      overlays,
      fixed_elements: fixedElements,
      sticky_elements: stickyElements,
      visual_elements: visualElements,
      mappings,
      indexes,
      privacy_mode: privacyMode,
      metadata: {
        total_visual_elements: visualElements.length,
        total_regions: regions.length,
        total_overlays: overlays.length,
        total_fixed: fixedElements.length,
        total_sticky: stickyElements.length,
        sensitive_redacted_count: redactedCount
      }
    };

    this.lastVisualModel = model;
    return model;
  }

  private buildIndexes(
    visualElements: VisualPageModel['visual_elements'],
    regions: VisualPageModel['regions']
  ): VisualPageIndexes {
    const indexes: VisualPageIndexes = {
      byVisualType: {},
      bySemanticElement: {},
      byRegion: {},
      byInteractive: [],
      byVisibility: {
        fully_visible: [],
        partially_visible: [],
        outside_viewport: [],
        hidden: []
      }
    };

    for (const el of visualElements) {
      // byVisualType
      const t = el.type.toLowerCase();
      if (!indexes.byVisualType[t]) indexes.byVisualType[t] = [];
      indexes.byVisualType[t].push(el.visual_id);

      // bySemanticElement
      if (el.semantic_element_id) {
        indexes.bySemanticElement[el.semantic_element_id] = el.visual_id;
      }

      // byInteractive
      if (el.is_interactive) {
        indexes.byInteractive.push(el.visual_id);
      }

      // byVisibility
      if (indexes.byVisibility[el.visibility]) {
        indexes.byVisibility[el.visibility].push(el.visual_id);
      }
    }

    // byRegion
    for (const reg of regions) {
      indexes.byRegion[reg.region_id] = reg.visual_element_ids;
    }

    return indexes;
  }
}

export const visualEngine = new VisualEngine();
