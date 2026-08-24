/**
 * MATRIOSHAI Visual DOM Extractor (Phase 6)
 *
 * Extracts visual layout hierarchy, visual element bounding boxes, canvas/SVG/image/video
 * elements, fixed/sticky elements, visual overlays/dialogs, z-index stacking,
 * and regional grouping.
 */

import {
  type VisualElement,
  type VisualElementType,
  type VisualRegion,
  type VisualRegionType,
  type VisualOverlay,
  type FixedElement,
  type VisualElementMapping,
  type ViewportMetrics,
  type SemanticElement,
  type VisualBoundingBox
} from '../shared/types';
import { VisualGeometry } from './visual-geometry';

export class VisualExtractor {
  private visualCounter = 0;

  public extractVisuals(
    viewport: ViewportMetrics,
    semanticElements: SemanticElement[],
    dpr: number = 1.0,
    scaleFactor: number = 1.0
  ): {
    visualElements: VisualElement[];
    regions: VisualRegion[];
    overlays: VisualOverlay[];
    fixedElements: FixedElement[];
    stickyElements: FixedElement[];
    mappings: VisualElementMapping[];
  } {
    this.visualCounter = 0;

    const visualElements: VisualElement[] = [];
    const overlays: VisualOverlay[] = [];
    const fixedElements: FixedElement[] = [];
    const stickyElements: FixedElement[] = [];
    const mappings: VisualElementMapping[] = [];

    // Map semantic elements to visual elements
    for (const sem of semanticElements) {
      const domEl = document.querySelector(`[data-matrioshai-id="${sem.element_id}"]`) as HTMLElement;
      let domBox: VisualBoundingBox;

      if (sem.bounding_box.width > 0 && sem.bounding_box.height > 0) {
        domBox = VisualGeometry.createBox(
          sem.bounding_box.x,
          sem.bounding_box.y,
          sem.bounding_box.width,
          sem.bounding_box.height,
          'DOM_VIEWPORT'
        );
      } else if (domEl) {
        const b = this.getElementBounds(domEl);
        domBox = VisualGeometry.createBox(b.x, b.y, b.width, b.height, 'DOM_VIEWPORT');
      } else {
        domBox = VisualGeometry.createBox(0, 0, 100, 36, 'DOM_VIEWPORT');
      }

      const screenshotBox = VisualGeometry.domToScreenshotCoordinates(domBox, dpr, scaleFactor);
      const visibility = VisualGeometry.classifyVisibility(domBox, viewport.width, viewport.height);

      const zIndex = this.computeZIndex(domEl);
      const pos = this.computePositionType(domEl);
      const isFixed = pos === 'fixed';
      const isSticky = pos === 'sticky';

      const visualId = `vis_${this.visualCounter++}`;
      const visualType = this.mapSemanticToVisualType(sem);

      const vEl: VisualElement = {
        visual_id: visualId,
        semantic_element_id: sem.element_id,
        type: visualType,
        tag_name: sem.tag_name,
        role: sem.role,
        name: sem.name,
        dom_box: domBox,
        screenshot_box: screenshotBox,
        visibility,
        z_index: zIndex,
        is_interactive: true,
        is_fixed: isFixed,
        is_sticky: isSticky,
        is_canvas: false,
        is_svg: false,
        is_image: sem.tag_name === 'img',
        is_video: sem.tag_name === 'video',
        confidence: sem.confidence,
        source: 'dom_mapped',
        state: {
          disabled: !sem.enabled,
          focused: sem.focused,
          selected: sem.selected,
          expanded: sem.expanded,
          checked: sem.checked
        },
        attributes: sem.attributes
      };

      visualElements.push(vEl);

      mappings.push({
        element_id: sem.element_id,
        visual_id: visualId,
        dom_box: domBox,
        screenshot_box: screenshotBox,
        confidence: sem.confidence,
        visibility,
        occluded: false,
        partially_occluded: false,
        z_index: zIndex
      });

      if (isFixed) {
        fixedElements.push({
          element_id: sem.element_id,
          visual_id: visualId,
          bounding_box: domBox,
          screenshot_box: screenshotBox,
          z_index: zIndex,
          position_type: 'fixed'
        });
      }
      if (isSticky) {
        stickyElements.push({
          element_id: sem.element_id,
          visual_id: visualId,
          bounding_box: domBox,
          screenshot_box: screenshotBox,
          z_index: zIndex,
          position_type: 'sticky'
        });
      }
    }

    // Extract visual-only media elements (Canvases, SVGs, Images, Videos not already captured)
    this.extractMediaElements(visualElements, viewport, dpr, scaleFactor);

    // Extract overlays & dialogs
    this.extractOverlays(overlays, visualElements, dpr, scaleFactor);

    // Extract visual regions & hierarchy
    const regions = this.extractRegions(visualElements, dpr, scaleFactor, fixedElements, stickyElements);

    // Compute basic occlusion
    this.computeOcclusions(mappings, visualElements);

    return {
      visualElements,
      regions,
      overlays,
      fixedElements,
      stickyElements,
      mappings
    };
  }

  private extractMediaElements(
    visualElements: VisualElement[],
    viewport: ViewportMetrics,
    dpr: number,
    scaleFactor: number
  ): void {
    const mediaNodes = document.querySelectorAll('canvas, svg, img, video');

    mediaNodes.forEach((node) => {
      const el = node as HTMLElement;
      // Skip if already mapped as interactive
      if (el.hasAttribute('data-matrioshai-id')) return;

      const bounds = this.getElementBounds(el);
      const tagName = el.tagName.toLowerCase();
      const domBox = VisualGeometry.createBox(bounds.x, bounds.y, bounds.width, bounds.height, 'DOM_VIEWPORT');
      const screenshotBox = VisualGeometry.domToScreenshotCoordinates(domBox, dpr, scaleFactor);
      const visibility = VisualGeometry.classifyVisibility(domBox, viewport.width, viewport.height);
      const zIndex = this.computeZIndex(el);

      let visualType: VisualElementType = 'UNKNOWN';
      let isCanvas = false;
      let isSvg = false;
      let isImage = false;
      let isVideo = false;

      if (tagName === 'canvas') {
        visualType = 'CANVAS';
        isCanvas = true;
      } else if (tagName === 'svg') {
        visualType = el.getAttribute('role') === 'button' ? 'BUTTON' : 'ICON';
        isSvg = true;
      } else if (tagName === 'img') {
        visualType = 'IMAGE';
        isImage = true;
      } else if (tagName === 'video') {
        visualType = 'VIDEO';
        isVideo = true;
      }

      const visualId = `vis_${this.visualCounter++}`;
      visualElements.push({
        visual_id: visualId,
        semantic_element_id: null,
        type: visualType,
        tag_name: tagName,
        role: el.getAttribute('role') || tagName,
        name: el.getAttribute('aria-label') || el.getAttribute('alt') || el.getAttribute('title') || null,
        dom_box: domBox,
        screenshot_box: screenshotBox,
        visibility,
        z_index: zIndex,
        is_interactive: false,
        is_fixed: this.computePositionType(el) === 'fixed',
        is_sticky: this.computePositionType(el) === 'sticky',
        is_canvas: isCanvas,
        is_svg: isSvg,
        is_image: isImage,
        is_video: isVideo,
        confidence: 'HIGH',
        source: 'dom_mapped',
        state: {},
        attributes: {
          id: el.id || '',
          class: el.className || ''
        }
      });
    });
  }

  private extractOverlays(
    overlays: VisualOverlay[],
    visualElements: VisualElement[],
    dpr: number,
    scaleFactor: number
  ): void {
    const dialogNodes = document.querySelectorAll('dialog, [role="dialog"], [role="alertdialog"], .modal, .popup');

    dialogNodes.forEach((node, idx) => {
      const el = node as HTMLElement;
      const bounds = this.getElementBounds(el);

      const domBox = VisualGeometry.createBox(bounds.x, bounds.y, bounds.width, bounds.height, 'DOM_VIEWPORT');
      const screenshotBox = VisualGeometry.domToScreenshotCoordinates(domBox, dpr, scaleFactor);
      const zIndex = this.computeZIndex(el);

      const isDialogRole = el.getAttribute('role') === 'alertdialog' || el.getAttribute('role') === 'dialog' || el.tagName.toLowerCase() === 'dialog';
      const overlayType = isDialogRole ? 'dialog' : 'modal';

      const childVisualIds = visualElements
        .filter((ve) => VisualGeometry.containsRect(domBox, ve.dom_box))
        .map((ve) => ve.visual_id);

      overlays.push({
        overlay_id: el.id || `overlay_${idx}`,
        visual_id: `vis_ov_${idx}`,
        type: overlayType,
        bounding_box: domBox,
        screenshot_box: screenshotBox,
        z_index: Math.max(zIndex, 100),
        is_visible: true,
        child_visual_ids: childVisualIds
      });
    });
  }

  private extractRegions(
    visualElements: VisualElement[],
    dpr: number,
    scaleFactor: number,
    fixedElements: FixedElement[],
    stickyElements: FixedElement[]
  ): VisualRegion[] {
    const regions: VisualRegion[] = [];
    const regionSelectors = [
      { selector: 'header, [role="banner"]', type: 'HEADER' as VisualRegionType },
      { selector: 'nav, [role="navigation"]', type: 'NAVIGATION' as VisualRegionType },
      { selector: 'main, [role="main"]', type: 'MAIN' as VisualRegionType },
      { selector: 'aside, [role="complementary"]', type: 'SIDEBAR' as VisualRegionType },
      { selector: 'footer, [role="contentinfo"]', type: 'FOOTER' as VisualRegionType },
      { selector: 'form, [role="search"]', type: 'SEARCH' as VisualRegionType }
    ];

    let regionIndex = 0;
    for (const { selector, type } of regionSelectors) {
      const nodes = document.querySelectorAll(selector);
      nodes.forEach((node) => {
        const el = node as HTMLElement;
        const bounds = this.getElementBounds(el);

        const domBox = VisualGeometry.createBox(bounds.x, bounds.y, bounds.width, bounds.height, 'DOM_VIEWPORT');
        const screenshotBox = VisualGeometry.domToScreenshotCoordinates(domBox, dpr, scaleFactor);
        const zIndex = this.computeZIndex(el);
        const pos = this.computePositionType(el);

        const childVisualIds = visualElements
          .filter((ve) => VisualGeometry.containsRect(domBox, ve.dom_box))
          .map((ve) => ve.visual_id);

        const regionId = el.id || `reg_${regionIndex++}`;
        regions.push({
          region_id: regionId,
          type,
          label: el.getAttribute('aria-label') || null,
          bounding_box: domBox,
          screenshot_box: screenshotBox,
          z_index: zIndex,
          is_fixed: pos === 'fixed',
          is_sticky: pos === 'sticky',
          element_ids: [],
          visual_element_ids: childVisualIds
        });

        if (pos === 'fixed') {
          fixedElements.push({
            element_id: regionId,
            visual_id: `vis_${regionId}`,
            bounding_box: domBox,
            screenshot_box: screenshotBox,
            z_index: zIndex,
            position_type: 'fixed'
          });
        }
        if (pos === 'sticky') {
          stickyElements.push({
            element_id: regionId,
            visual_id: `vis_${regionId}`,
            bounding_box: domBox,
            screenshot_box: screenshotBox,
            z_index: zIndex,
            position_type: 'sticky'
          });
        }
      });
    }

    return regions;
  }

  private getElementBounds(el: HTMLElement): { x: number; y: number; width: number; height: number } {
    const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { x: 0, y: 0, width: 0, height: 0 };
    const attrW = parseInt(el.getAttribute('width') || '0', 10);
    const attrH = parseInt(el.getAttribute('height') || '0', 10);
    const styleW = parseInt(el.style?.width || '0', 10);
    const styleH = parseInt(el.style?.height || '0', 10);

    const width = rect.width > 0 ? rect.width : (attrW > 0 ? attrW : (styleW > 0 ? styleW : (el.offsetWidth || 100)));
    const height = rect.height > 0 ? rect.height : (attrH > 0 ? attrH : (styleH > 0 ? styleH : (el.offsetHeight || 40)));
    const x = rect.x || parseInt(el.style?.left || '0', 10) || 0;
    const y = rect.y || parseInt(el.style?.top || '0', 10) || 0;

    return { x, y, width, height };
  }

  private computeOcclusions(mappings: VisualElementMapping[], elements: VisualElement[]): void {
    for (let i = 0; i < mappings.length; i++) {
      const map = mappings[i];
      for (let j = 0; j < elements.length; j++) {
        const other = elements[j];
        if (map.visual_id === other.visual_id) continue;

        if (other.z_index > map.z_index && VisualGeometry.intersectsRect(map.dom_box, other.dom_box)) {
          if (VisualGeometry.containsRect(other.dom_box, map.dom_box)) {
            map.occluded = true;
          } else {
            map.partially_occluded = true;
          }
        }
      }
    }
  }

  private computeZIndex(el: HTMLElement | null): number {
    if (!el) return 0;
    try {
      let curr: HTMLElement | null = el;
      while (curr && curr !== document.body) {
        if (curr.style && curr.style.zIndex) {
          const z = parseInt(curr.style.zIndex, 10);
          if (!isNaN(z)) return z;
        }
        if (typeof window.getComputedStyle !== 'undefined') {
          const style = window.getComputedStyle(curr);
          const z = parseInt(style.zIndex, 10);
          if (!isNaN(z)) return z;
        }
        curr = curr.parentElement;
      }
      return 0;
    } catch {
      return 0;
    }
  }

  private computePositionType(el: HTMLElement | null): 'fixed' | 'sticky' | 'normal' {
    if (!el) return 'normal';
    try {
      if (el.style) {
        if (el.style.position === 'fixed') return 'fixed';
        if (el.style.position === 'sticky') return 'sticky';
      }
      if (typeof window.getComputedStyle !== 'undefined') {
        const style = window.getComputedStyle(el);
        if (style.position === 'fixed') return 'fixed';
        if (style.position === 'sticky') return 'sticky';
      }
      return 'normal';
    } catch {
      return 'normal';
    }
  }

  private mapSemanticToVisualType(sem: SemanticElement): VisualElementType {
    switch (sem.semantic_type) {
      case 'BUTTON':
      case 'SUBMIT':
        return 'BUTTON';
      case 'TEXT':
      case 'EMAIL':
      case 'PASSWORD':
      case 'PHONE':
      case 'NUMBER':
      case 'DATE':
      case 'TIME':
      case 'DATETIME':
      case 'URL':
      case 'SEARCH':
      case 'TEXTAREA':
        return 'INPUT';
      case 'CHECKBOX':
        return 'CHECKBOX';
      case 'RADIO':
        return 'RADIO';
      case 'SELECT':
      case 'COMBOBOX':
        return 'MENU';
      case 'TAB':
        return 'TAB';
      case 'LINK':
        return 'LINK';
      case 'OPTION':
        return 'BUTTON';
      default:
        return sem.role === 'button' ? 'BUTTON' : (sem.role === 'link' ? 'LINK' : 'TEXT');
    }
  }
}

export const visualExtractor = new VisualExtractor();
