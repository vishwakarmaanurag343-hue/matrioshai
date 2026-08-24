// @vitest-environment happy-dom
import { describe, it, expect, beforeEach } from 'vitest';
import { WorldModelExtractor } from '../content/world-model-extractor';
import { PageObservationEngine } from '../content/observation-engine';
import { SemanticPageAnalyzer } from '../content/semantic-analyzer';
import { VisualEngine } from '../content/visual-engine';
import { type WorldElementRef } from '../shared/types';

describe('MATRIOSHAI Unified Browser World Model Extractor (Phase 7)', () => {
  let worldExtractor: WorldModelExtractor;
  let obsEngine: PageObservationEngine;
  let semAnalyzer: SemanticPageAnalyzer;
  let visEngine: VisualEngine;

  beforeEach(() => {
    worldExtractor = new WorldModelExtractor();
    obsEngine = new PageObservationEngine();
    semAnalyzer = new SemanticPageAnalyzer();
    visEngine = new VisualEngine();

    document.body.innerHTML = `
      <header role="banner" id="site-header" style="position: fixed; top: 0; left: 0; width: 1000px; height: 60px;">
        <h1 style="top: 10px; left: 10px; width: 200px; height: 40px;">Booking Portal</h1>
      </header>

      <main role="main" id="main-content" style="margin-top: 70px;">
        <form role="search" id="booking-form">
          <label for="origin-input">Departure City</label>
          <input type="text" id="origin-input" name="origin" value="SFO" style="top: 100px; left: 20px; width: 150px; height: 35px;" />

          <button type="submit" id="btn-submit-booking" style="top: 100px; left: 200px; width: 120px; height: 35px;">Search Flights</button>
        </form>

        <dialog id="promo-modal" open role="dialog" aria-label="Summer Deals" style="position: fixed; top: 150px; left: 150px; width: 400px; height: 200px;">
          <h2>Exclusive Discounts</h2>
          <button type="button" id="btn-claim-deal">Claim Deal</button>
        </dialog>

        <iframe id="partner-frame" src="about:blank" title="Partner Offers"></iframe>
      </main>
    `;
  });

  it('extracts local WorldPageState with viewport, scroll, dialog, and lifecycle metrics', () => {
    const obs = obsEngine.extractPageObservation(101);
    const sem = semAnalyzer.analyzePage(101, obs.observation_id);
    const vis = visEngine.generateVisualModel(101);

    const pageState = worldExtractor.extractWorldPageState(101, obs, sem, vis);

    expect(pageState.tab_id).toBe(101);
    expect(pageState.page_id).toMatch(/^page_/);
    expect(pageState.page_version).toBe(1);
    expect(pageState.ready_state).toBe('complete');
    expect(pageState.active_dialogs).toContain('promo-modal');
    expect(pageState.has_overlay).toBe(true);
    expect(pageState.lifecycle).toBe('READY');
    expect(pageState.observation_id).toBe(obs.observation_id);
    expect(pageState.semantic_model_id).toBe(sem.semantic_model_id);
    expect(pageState.visual_model_id).toBe(vis.visual_model_id);
  });

  it('extracts FrameTree representation separating main and child frames', () => {
    const tree = worldExtractor.extractFrameTree(101);

    expect(tree.tab_id).toBe(101);
    expect(tree.frame_count).toBe(2);
    expect(tree.root_frame.frame.frame_id).toBe('frame_main_0');
    expect(tree.root_frame.frame.accessible).toBe(true);
    expect(tree.root_frame.children.length).toBe(1);
    expect(tree.root_frame.children[0].frame.frame_id).toBe('partner-frame');
  });

  it('synthesizes unified WorldElements unifying DOM, Semantic, and Visual states', () => {
    const obs = obsEngine.extractPageObservation(101);
    const sem = semAnalyzer.analyzePage(101, obs.observation_id);
    const vis = visEngine.generateVisualModel(101);

    const elements = worldExtractor.synthesizeWorldElements(sem, vis);

    expect(elements.length).toBeGreaterThanOrEqual(2);
    const searchBtn = elements.find((e) => e.element_ref.stable_dom_identity === 'btn-submit-booking');
    expect(searchBtn).toBeDefined();
    expect(searchBtn?.role).toBe('button');
    expect(searchBtn?.name).toBe('Search Flights');
    expect(searchBtn?.visible).toBe(true);
    expect(searchBtn?.enabled).toBe(true);
    expect(searchBtn?.source).toBe('visual_engine');
  });

  it('resolves WorldElementRefs and detects STALE or PAGE_CHANGED states', () => {
    const obs = obsEngine.extractPageObservation(101);
    const sem = semAnalyzer.analyzePage(101, obs.observation_id);
    const vis = visEngine.generateVisualModel(101);
    const elements = worldExtractor.synthesizeWorldElements(sem, vis);

    const searchBtn = elements.find((e) => e.element_ref.stable_dom_identity === 'btn-submit-booking')!;
    const ref = { ...searchBtn.element_ref };

    // 1. Exact match resolution
    const resExact = worldExtractor.resolveWorldElement(ref, elements);
    expect(resExact.status).toBe('FOUND');
    expect(resExact.element?.name).toBe('Search Flights');

    // 2. Stale reference resolution (page version incremented)
    worldExtractor.incrementPageVersion();
    const resStale = worldExtractor.resolveWorldElement(ref, elements);
    expect(resStale.status).toBe('STALE');
    expect(resStale.candidates.length).toBeGreaterThanOrEqual(1);

    // 3. Page changed resolution (different page ID)
    const refOtherPage: WorldElementRef = {
      ...ref,
      page_id: 'page_old_navigation_999'
    };
    const resPageChanged = worldExtractor.resolveWorldElement(refOtherPage, elements);
    expect(resPageChanged.status).toBe('PAGE_CHANGED');
  });
});
