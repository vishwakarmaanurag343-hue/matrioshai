import { createScopedLogger } from '../shared/logger';
import { semanticPageAnalyzer } from './semantic-analyzer';
import { visualEngine } from './visual-engine';
import { worldModelExtractor } from './world-model-extractor';

const logger = createScopedLogger('MUTATION_TRACKER');

export class DomMutationTracker {
  private observer: MutationObserver | null = null;
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private isObserving = false;
  private handleResizeOrScroll: (() => void) | null = null;

  public start(): void {
    if (this.isObserving) {
      return;
    }

    if (typeof MutationObserver !== 'undefined' && document.body) {
      try {
        this.observer = new MutationObserver((mutations) => {
          let hasStructuralChange = false;

          for (const m of mutations) {
            // Ignore our own attribute injections
            if (m.type === 'attributes' && m.attributeName === 'data-matrioshai-id') {
              continue;
            }
            if (m.addedNodes.length > 0 || m.removedNodes.length > 0) {
              hasStructuralChange = true;
              break;
            }
          }

          if (hasStructuralChange) {
            this.scheduleInvalidation();
          }
        });

        this.observer.observe(document.body, {
          childList: true,
          subtree: true,
          attributes: false
        });

        logger.debug('DOM Mutation Tracker active');
      } catch (err) {
        logger.debug('Could not initialize MutationObserver', err);
      }
    }

    // Invalidate visual models when viewport resizes or scrolls
    if (typeof window !== 'undefined' && window.addEventListener) {
      this.handleResizeOrScroll = () => {
        this.scheduleInvalidation();
      };
      window.addEventListener('resize', this.handleResizeOrScroll, { passive: true });
      window.addEventListener('scroll', this.handleResizeOrScroll, { passive: true });
    }

    this.isObserving = true;
  }

  public stop(): void {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
    if (this.handleResizeOrScroll && typeof window !== 'undefined' && window.removeEventListener) {
      window.removeEventListener('resize', this.handleResizeOrScroll);
      window.removeEventListener('scroll', this.handleResizeOrScroll);
      this.handleResizeOrScroll = null;
    }
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    this.isObserving = false;
  }

  private scheduleInvalidation(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = setTimeout(() => {
      semanticPageAnalyzer.invalidateModel();
      visualEngine.invalidateModel();
      worldModelExtractor.incrementPageVersion();
      logger.debug('Page semantic, visual, and world models invalidated due to DOM mutation/resize/scroll');
    }, 200);
  }
}

export const domMutationTracker = new DomMutationTracker();
