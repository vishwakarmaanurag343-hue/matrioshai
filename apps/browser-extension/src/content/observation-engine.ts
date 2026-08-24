/**
 * MATRIOSHAI Page Observation Engine (Phase 4)
 *
 * Runs inside the browser webpage context (Content Script).
 * Extracts clean, normalized, structured PageObservation without returning raw unparsed HTML.
 * Normalizes viewport metrics, visible text blocks, semantic headings/landmarks,
 * interactive elements with bounding boxes and visibility states, and frame hierarchies.
 */

import {
  type PageObservation,
  type ViewportMetrics,
  type InteractiveElement,
  type HeadingElement,
  type LandmarkElement,
  type FrameElement,
  type BoundingBox
} from '../shared/types';

export class PageObservationEngine {
  private elementCounter = 0;

  /**
   * Extract complete structured PageObservation of the current document
   */
  public extractPageObservation(tabId: number = 0): PageObservation {
    this.elementCounter = 0;
    const observationId = `obs_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

    const viewport = this.extractViewport();
    const visibleText = this.extractVisibleText();
    const headings = this.extractHeadings();
    const landmarks = this.extractLandmarks();
    const interactiveElements = this.extractInteractiveElements(viewport);
    const frames = this.extractFrames();

    const documentState: 'loading' | 'interactive' | 'complete' =
      document.readyState === 'loading'
        ? 'loading'
        : document.readyState === 'interactive'
        ? 'interactive'
        : 'complete';

    return {
      observation_id: observationId,
      tab_id: tabId,
      url: window.location.href,
      title: document.title || '',
      document_state: documentState,
      timestamp: new Date().toISOString(),
      viewport,
      visible_text: visibleText,
      headings,
      landmarks,
      interactive_elements: interactiveElements,
      frames
    };
  }

  /**
   * Extract viewport dimensions and document scroll metrics
   */
  private extractViewport(): ViewportMetrics {
    const width = window.innerWidth || document.documentElement.clientWidth || 0;
    const height = window.innerHeight || document.documentElement.clientHeight || 0;
    const scrollX = window.scrollX ?? window.pageXOffset ?? 0;
    const scrollY = window.scrollY ?? window.pageYOffset ?? 0;
    const documentWidth = Math.max(
      document.documentElement.scrollWidth,
      document.body?.scrollWidth || 0,
      width
    );
    const documentHeight = Math.max(
      document.documentElement.scrollHeight,
      document.body?.scrollHeight || 0,
      height
    );

    return {
      width,
      height,
      scroll_x: scrollX,
      scroll_y: scrollY,
      document_width: documentWidth,
      document_height: documentHeight
    };
  }

  /**
   * Extract clean visible text blocks from page content
   */
  private extractVisibleText(): string[] {
    const textBlocks: string[] = [];
    const seen = new Set<string>();

    const textNodes = document.querySelectorAll(
      'h1, h2, h3, h4, h5, h6, p, li, blockquote, figcaption, article, section, [role="article"]'
    );

    for (const node of Array.from(textNodes)) {
      const el = node as HTMLElement;
      if (!this.isElementVisible(el)) continue;

      // Extract direct or child text content, collapsing excessive whitespace
      const text = el.innerText?.replace(/\s+/g, ' ').trim();
      if (text && text.length > 1 && !seen.has(text)) {
        seen.add(text);
        textBlocks.push(text);
        if (textBlocks.length >= 100) break; // Reasonable bounded extraction
      }
    }

    // Fallback if structured selectors returned nothing (e.g. simple <body> text)
    if (textBlocks.length === 0 && document.body) {
      const bodyText = document.body.innerText?.replace(/\s+/g, ' ').trim();
      if (bodyText) {
        textBlocks.push(bodyText.slice(0, 500));
      }
    }

    return textBlocks;
  }

  /**
   * Extract semantic headings (h1 - h6)
   */
  private extractHeadings(): HeadingElement[] {
    const headings: HeadingElement[] = [];
    const elements = document.querySelectorAll('h1, h2, h3, h4, h5, h6');

    for (const el of Array.from(elements)) {
      const h = el as HTMLElement;
      if (!this.isElementVisible(h)) continue;

      const level = parseInt(h.tagName.substring(1), 10) || 1;
      const text = h.innerText?.replace(/\s+/g, ' ').trim() || '';
      if (text) {
        headings.push({
          level,
          text,
          id: h.id || null
        });
      }
    }

    return headings;
  }

  /**
   * Extract landmark regions (header, nav, main, footer, section, article)
   */
  private extractLandmarks(): LandmarkElement[] {
    const landmarks: LandmarkElement[] = [];
    const elements = document.querySelectorAll(
      'header, nav, main, footer, article, section, aside, [role="banner"], [role="navigation"], [role="main"], [role="contentinfo"], [role="search"]'
    );

    for (const el of Array.from(elements)) {
      const h = el as HTMLElement;
      if (!this.isElementVisible(h)) continue;

      const role = h.getAttribute('role') || h.tagName.toLowerCase();
      const label = h.getAttribute('aria-label') || h.getAttribute('title') || null;

      landmarks.push({
        role,
        tag_name: h.tagName.toLowerCase(),
        label
      });
      if (landmarks.length >= 30) break;
    }

    return landmarks;
  }

  /**
   * Extract and normalize interactive elements (links, buttons, inputs, ARIA widgets)
   */
  private extractInteractiveElements(viewport: ViewportMetrics): InteractiveElement[] {
    const interactive: InteractiveElement[] = [];
    const selector = [
      'a[href]',
      'button',
      'input:not([type="hidden"])',
      'textarea',
      'select',
      '[role="button"]',
      '[role="link"]',
      '[role="checkbox"]',
      '[role="radio"]',
      '[role="combobox"]',
      '[role="menuitem"]',
      '[role="tab"]',
      '[tabindex]:not([tabindex="-1"])',
      '[onclick]'
    ].join(', ');

    const elements = document.querySelectorAll(selector);

    for (const rawEl of Array.from(elements)) {
      const el = rawEl as HTMLElement;
      const isVisible = this.isElementVisible(el);
      if (!isVisible) continue;

      let rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { x: 0, y: 0, width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 };
      
      const isInViewport =
        rect.bottom >= 0 &&
        rect.top <= (viewport.height || 1000) &&
        rect.right >= 0 &&
        rect.left <= (viewport.width || 1200);

      const elementId = this.assignElementId(el);
      const tagName = el.tagName.toLowerCase();
      const role = el.getAttribute('role') || this.getDefaultRole(tagName, el);
      const text = this.getElementText(el);
      const isEnabled = !(el as HTMLButtonElement).disabled && el.getAttribute('aria-disabled') !== 'true';

      const boundingBox: BoundingBox = {
        x: Math.round(rect.x || 0),
        y: Math.round(rect.y || 0),
        width: Math.round(rect.width || (rect.right ? rect.right - rect.left : 0)),
        height: Math.round(rect.height || (rect.bottom ? rect.bottom - rect.top : 0)),
        top: Math.round(rect.top || 0),
        left: Math.round(rect.left || 0),
        right: Math.round(rect.right || 0),
        bottom: Math.round(rect.bottom || 0)
      };

      const attributes: Record<string, string> = {};
      if (el.id) attributes.id = el.id;
      if (el.getAttribute('name')) attributes.name = el.getAttribute('name')!;
      if (el.getAttribute('aria-label')) attributes['aria-label'] = el.getAttribute('aria-label')!;
      if (el.getAttribute('title')) attributes.title = el.getAttribute('title')!;

      const item: InteractiveElement = {
        element_id: elementId,
        tag_name: tagName,
        role,
        text,
        bounding_box: boundingBox,
        is_visible: isVisible,
        is_in_viewport: isInViewport,
        is_enabled: isEnabled,
        attributes
      };

      if (tagName === 'a') {
        item.href = (el as HTMLAnchorElement).href || el.getAttribute('href') || null;
      }

      if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') {
        const inputEl = el as HTMLInputElement;
        item.input_type = inputEl.type || 'text';
        item.placeholder = inputEl.placeholder || null;
        if (inputEl.type !== 'password') {
          item.value = inputEl.value || null;
        } else {
          item.value = inputEl.value ? '[MASKED_PASSWORD]' : null;
        }
      }

      interactive.push(item);
      if (interactive.length >= 150) break; // Limit to first 150 relevant elements
    }

    return interactive;
  }

  /**
   * Extract child iframe metadata
   */
  private extractFrames(): FrameElement[] {
    const frames: FrameElement[] = [];
    const iframes = document.querySelectorAll('iframe, frame');

    for (const raw of Array.from(iframes)) {
      const f = raw as HTMLIFrameElement;
      const src = f.src || f.getAttribute('src') || '';
      let isCrossOrigin = false;

      try {
        if (src && !src.startsWith('about:') && !src.startsWith('javascript:')) {
          const frameUrl = new URL(src, window.location.href);
          isCrossOrigin = frameUrl.origin !== window.location.origin;
        }
      } catch {
        isCrossOrigin = true;
      }

      frames.push({
        frame_id: f.id || `frame_${frames.length}`,
        src,
        name: f.name || null,
        is_cross_origin: isCrossOrigin
      });
    }

    return frames;
  }

  /**
   * Assign deterministic matrioshai ID to DOM element
   */
  private assignElementId(el: HTMLElement): string {
    const existing = el.getAttribute('data-matrioshai-id');
    if (existing) return existing;

    const id = `el_${this.elementCounter++}`;
    el.setAttribute('data-matrioshai-id', id);
    return id;
  }

  /**
   * Check if element is visually rendered (not display:none, opacity > 0, etc.)
   */
  private isElementVisible(el: HTMLElement): boolean {
    if (typeof window.getComputedStyle === 'undefined') return true;
    try {
      const style = window.getComputedStyle(el);
      if (style.display === 'none') return false;
      if (style.visibility === 'hidden' || style.visibility === 'collapse') return false;
      if (parseFloat(style.opacity) <= 0) return false;
      return true;
    } catch {
      return true;
    }
  }

  /**
   * Extract meaningful text label from interactive element
   */
  private getElementText(el: HTMLElement): string {
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim();

    const title = el.getAttribute('title');
    if (title && title.trim()) return title.trim();

    const placeholder = el.getAttribute('placeholder');
    if (placeholder && placeholder.trim()) return placeholder.trim();

    const innerText = el.innerText;
    if (innerText && innerText.trim()) {
      return innerText.replace(/\s+/g, ' ').trim().slice(0, 100);
    }

    const value = (el as HTMLInputElement).value;
    if (value && typeof value === 'string' && value.trim()) {
      return value.trim().slice(0, 100);
    }

    const alt = el.getAttribute('alt');
    if (alt && alt.trim()) return alt.trim();

    return '';
  }

  private getDefaultRole(tagName: string, el: HTMLElement): string {
    switch (tagName) {
      case 'a':
        return el.getAttribute('href') ? 'link' : 'generic';
      case 'button':
        return 'button';
      case 'input': {
        const type = (el as HTMLInputElement).type;
        if (type === 'checkbox') return 'checkbox';
        if (type === 'radio') return 'radio';
        if (type === 'submit' || type === 'button') return 'button';
        return 'textbox';
      }
      case 'textarea':
        return 'textbox';
      case 'select':
        return 'combobox';
      default:
        return 'widget';
    }
  }
}

export const pageObservationEngine = new PageObservationEngine();
