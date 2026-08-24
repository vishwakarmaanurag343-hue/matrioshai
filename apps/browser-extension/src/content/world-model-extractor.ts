/**
 * MATRIOSHAI World Model Extractor (Phase 7)
 *
 * Synthesizes DOM observations (Phase 4), Semantic Models (Phase 5),
 * and Visual Intelligence (Phase 6) into cohesive WorldPageState,
 * unified WorldElement representations, and frame trees.
 */

import {
  type WorldPageState,
  type WorldFrameState,
  type FrameTree,
  type FrameTreeNode,
  type WorldElement,
  type WorldElementRef,
  type WorldElementResolution,
  type PageObservation,
  type SemanticPageModel,
  type VisualPageModel,
  type VisualElement
} from '../shared/types';
import { VisualGeometry } from './visual-geometry';

export class WorldModelExtractor {
  private pageVersion = 1;
  private currentUrl = '';
  private currentOrigin = '';
  private pageId = '';

  constructor() {
    this.initPageIdentity();
  }

  private initPageIdentity(): void {
    if (typeof window !== 'undefined') {
      this.currentUrl = window.location.href;
      this.currentOrigin = window.location.origin;
      this.pageId = `page_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    }
  }

  public getPageId(): string {
    return this.pageId;
  }

  public getPageVersion(): number {
    return this.pageVersion;
  }

  public incrementPageVersion(): number {
    this.pageVersion += 1;
    return this.pageVersion;
  }

  public resetPageIdentity(): void {
    this.initPageIdentity();
    this.pageVersion = 1;
  }

  /**
   * Extract comprehensive local WorldPageState
   */
  public extractWorldPageState(
    tabId: number,
    observation?: PageObservation | null,
    semanticModel?: SemanticPageModel | null,
    visualModel?: VisualPageModel | null
  ): WorldPageState {
    // Check if SPA navigation changed the URL without reloading
    if (typeof window !== 'undefined' && window.location.href !== this.currentUrl) {
      this.currentUrl = window.location.href;
      this.currentOrigin = window.location.origin;
      this.incrementPageVersion();
    }

    const scrollX = typeof window !== 'undefined' ? Math.round(window.scrollX || window.pageXOffset || 0) : 0;
    const scrollY = typeof window !== 'undefined' ? Math.round(window.scrollY || window.pageYOffset || 0) : 0;
    const viewportWidth = typeof window !== 'undefined' ? window.innerWidth || 1280 : 1280;
    const viewportHeight = typeof window !== 'undefined' ? window.innerHeight || 800 : 800;

    let docWidth = viewportWidth;
    let docHeight = viewportHeight;
    if (typeof document !== 'undefined' && document.documentElement) {
      docWidth = Math.max(
        document.documentElement.scrollWidth || 0,
        document.documentElement.offsetWidth || 0,
        viewportWidth
      );
      docHeight = Math.max(
        document.documentElement.scrollHeight || 0,
        document.documentElement.offsetHeight || 0,
        viewportHeight
      );
    }

    const readyState = typeof document !== 'undefined' ? document.readyState : 'complete';
    const visibilityState = typeof document !== 'undefined' ? document.visibilityState : 'visible';
    const title = typeof document !== 'undefined' ? document.title : '';

    // Active dialogs
    const activeDialogs: string[] = [];
    if (typeof document !== 'undefined') {
      const dialogs = document.querySelectorAll('dialog[open], [role="dialog"]:not([aria-hidden="true"])');
      dialogs.forEach((d) => {
        activeDialogs.push(d.id || `dialog_${activeDialogs.length}`);
      });
    }

    // Focused element
    let focusedElementId: string | null = null;
    if (typeof document !== 'undefined' && document.activeElement) {
      focusedElementId = document.activeElement.getAttribute('data-matrioshai-id') || document.activeElement.id || null;
    }

    const hasOverlay = (visualModel?.overlays && visualModel.overlays.length > 0) || activeDialogs.length > 0;

    return {
      page_id: this.pageId,
      tab_id: tabId,
      url: this.currentUrl,
      origin: this.currentOrigin,
      title,
      ready_state: readyState,
      visibility_state: visibilityState,
      page_version: this.pageVersion,
      observation_id: observation?.observation_id || semanticModel?.observation_id || visualModel?.observation_id || null,
      semantic_model_id: semanticModel?.semantic_model_id || visualModel?.semantic_model_id || null,
      visual_model_id: visualModel?.visual_model_id || null,
      scroll_x: scrollX,
      scroll_y: scrollY,
      viewport_width: viewportWidth,
      viewport_height: viewportHeight,
      document_width: docWidth,
      document_height: docHeight,
      active_dialogs: activeDialogs,
      focused_element_id: focusedElementId,
      has_overlay: hasOverlay,
      lifecycle: readyState === 'complete' ? 'READY' : 'LOADING',
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Extract FrameTree representation
   */
  public extractFrameTree(tabId: number): FrameTree {
    const rootFrame: WorldFrameState = {
      frame_id: 'frame_main_0',
      parent_frame_id: null,
      tab_id: tabId,
      origin: this.currentOrigin,
      url: this.currentUrl,
      accessible: true,
      page_version: this.pageVersion,
      semantic_model_reference: null,
      visual_reference: null
    };

    const children: FrameTreeNode[] = [];
    if (typeof document !== 'undefined') {
      const iframes = document.querySelectorAll('iframe, frame');
      iframes.forEach((raw, idx) => {
        const iframe = raw as HTMLIFrameElement;
        let isAccessible = false;
        let origin = '';
        let src = iframe.src || iframe.getAttribute('src') || '';

        try {
          if (src && !src.startsWith('about:') && !src.startsWith('javascript:')) {
            const parsed = new URL(src, window.location.href);
            origin = parsed.origin;
            isAccessible = origin === this.currentOrigin;
          } else {
            origin = this.currentOrigin;
            isAccessible = true;
          }
        } catch {
          isAccessible = false;
        }

        const childFrame: WorldFrameState = {
          frame_id: iframe.id || `frame_child_${idx}`,
          parent_frame_id: rootFrame.frame_id,
          tab_id: tabId,
          origin,
          url: src,
          accessible: isAccessible,
          page_version: this.pageVersion
        };

        children.push({
          frame: childFrame,
          children: []
        });
      });
    }

    return {
      tab_id: tabId,
      root_frame: {
        frame: rootFrame,
        children
      },
      frame_count: 1 + children.length
    };
  }

  /**
   * Synthesize unified WorldElements from SemanticPageModel and VisualPageModel
   */
  public synthesizeWorldElements(
    semanticModel?: SemanticPageModel | null,
    visualModel?: VisualPageModel | null
  ): WorldElement[] {
    const worldElements: WorldElement[] = [];
    if (!semanticModel || !semanticModel.interactive_elements) {
      return worldElements;
    }

    const visualMap = new Map<string, VisualElement>();
    if (visualModel && visualModel.visual_elements) {
      for (const ve of visualModel.visual_elements) {
        if (ve.semantic_element_id) {
          visualMap.set(ve.semantic_element_id, ve);
        }
      }
    }

    for (const sem of semanticModel.interactive_elements) {
      const vEl = visualMap.get(sem.element_id);

      const ref: WorldElementRef = {
        page_id: this.pageId,
        observation_id: semanticModel.observation_id,
        element_id: sem.element_id,
        semantic_model_id: semanticModel.semantic_model_id,
        visual_id: vEl?.visual_id || null,
        tag_name: sem.tag_name,
        role: sem.role,
        name: sem.name,
        page_version: this.pageVersion,
        stable_dom_identity: sem.attributes.id || null
      };

      const geometry = vEl
        ? vEl.dom_box
        : VisualGeometry.createBox(
            sem.bounding_box.x,
            sem.bounding_box.y,
            sem.bounding_box.width,
            sem.bounding_box.height,
            'DOM_VIEWPORT'
          );

      const isVisible = vEl ? vEl.visibility === 'fully_visible' || vEl.visibility === 'partially_visible' : sem.visible;

      const worldEl: WorldElement = {
        element_ref: ref,
        role: sem.role,
        name: sem.name,
        semantic_state: {
          type: sem.semantic_type,
          description: sem.description,
          focused: sem.focused,
          disabled: !sem.enabled,
          required: sem.required,
          checked: sem.checked,
          expanded: sem.expanded,
          sensitive: sem.sensitive
        },
        visual_state: vEl
          ? {
              visual_id: vEl.visual_id,
              visibility: vEl.visibility,
              occluded: vEl.visibility === 'hidden' || vEl.z_index < 0,
              partially_occluded: vEl.visibility === 'partially_visible',
              z_index: vEl.z_index,
              is_canvas: vEl.is_canvas,
              is_svg: vEl.is_svg
            }
          : null,
        geometry,
        parent_ref: sem.parent_id || null,
        child_refs: sem.child_ids || [],
        visible: isVisible,
        enabled: sem.enabled,
        semantic_confidence: sem.confidence,
        visual_confidence: vEl?.confidence || 'MEDIUM',
        source: vEl ? 'visual_engine' : 'semantic_engine',
        page_version: this.pageVersion
      };

      worldElements.push(worldEl);
    }

    return worldElements;
  }

  /**
   * Deterministically resolve a WorldElementRef
   */
  public resolveWorldElement(
    ref: WorldElementRef,
    currentWorldElements: WorldElement[]
  ): WorldElementResolution {
    // 1. Page identity check
    if (ref.page_id && ref.page_id !== this.pageId) {
      return {
        status: 'PAGE_CHANGED',
        reference: ref,
        candidates: [],
        message: `Reference page_id '${ref.page_id}' does not match current page_id '${this.pageId}'. Page has navigated.`
      };
    }

    // 2. Page version check
    if (ref.page_version < this.pageVersion) {
      // Find possible candidate matches on the current page version
      const candidates = currentWorldElements
        .filter((el) => {
          if (ref.stable_dom_identity && el.element_ref.stable_dom_identity === ref.stable_dom_identity) return true;
          return el.role === ref.role && el.name === ref.name;
        })
        .map((el) => el.element_ref);

      return {
        status: 'STALE',
        reference: ref,
        candidates,
        message: `Reference version v${ref.page_version} is older than current page version v${this.pageVersion}. Model is stale.`
      };
    }

    // 3. Exact element_id match
    const exactMatch = currentWorldElements.find((el) => el.element_ref.element_id === ref.element_id);
    if (exactMatch) {
      return {
        status: 'FOUND',
        element: exactMatch,
        reference: ref,
        candidates: [exactMatch.element_ref],
        message: 'Successfully resolved unique world element'
      };
    }

    // 4. Stable DOM identity fallback match
    if (ref.stable_dom_identity) {
      const stableMatches = currentWorldElements.filter(
        (el) => el.element_ref.stable_dom_identity === ref.stable_dom_identity
      );
      if (stableMatches.length === 1 && stableMatches[0]) {
        return {
          status: 'FOUND',
          element: stableMatches[0],
          reference: ref,
          candidates: [stableMatches[0].element_ref],
          message: `Resolved via stable DOM identity #${ref.stable_dom_identity}`
        };
      } else if (stableMatches.length > 1) {
        return {
          status: 'AMBIGUOUS',
          reference: ref,
          candidates: stableMatches.map((m) => m.element_ref),
          message: `Multiple elements share stable DOM identity #${ref.stable_dom_identity}`
        };
      }
    }

    // 5. Semantic Role + Name search
    const roleNameMatches = currentWorldElements.filter((el) => el.role === ref.role && el.name === ref.name);
    if (roleNameMatches.length === 1 && roleNameMatches[0]) {
      return {
        status: 'FOUND',
        element: roleNameMatches[0],
        reference: ref,
        candidates: [roleNameMatches[0].element_ref],
        message: 'Resolved via role and accessible name match'
      };
    } else if (roleNameMatches.length > 1) {
      return {
        status: 'AMBIGUOUS',
        reference: ref,
        candidates: roleNameMatches.map((m) => m.element_ref),
        message: `Ambiguity detected: found ${roleNameMatches.length} matching elements with role='${ref.role}' and name='${ref.name}'`
      };
    }

    return {
      status: 'NOT_FOUND',
      reference: ref,
      candidates: [],
      message: `Element '${ref.element_id}' not found in current world state.`
    };
  }
}

export const worldModelExtractor = new WorldModelExtractor();
