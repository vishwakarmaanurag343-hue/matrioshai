// @vitest-environment happy-dom
import { describe, it, expect, beforeEach } from 'vitest';
import { VisualEngine } from '../content/visual-engine';
import { VisualQueryEngine } from '../content/visual-query-engine';
import { VisualRedactor } from '../content/visual-redactor';

describe('MATRIOSHAI Visual Page Engine & Visual Queries (Phase 6)', () => {
  let visualEngine: VisualEngine;
  let visualQueryEngine: VisualQueryEngine;
  let visualRedactor: VisualRedactor;

  beforeEach(() => {
    visualEngine = new VisualEngine();
    visualQueryEngine = new VisualQueryEngine();
    visualRedactor = new VisualRedactor();

    document.body.innerHTML = `
      <header role="banner" style="position: fixed; top: 0px; left: 0px; width: 1000px; height: 60px; z-index: 100;" id="site-header">
        <h1 style="top: 10px; left: 10px; width: 200px; height: 40px;">Flight Portal</h1>
        <nav role="navigation" id="site-nav" style="top: 10px; left: 300px; width: 200px; height: 40px;">
          <a href="/search" id="link-search" style="top: 10px; left: 300px; width: 80px; height: 30px;">Search</a>
          <a href="/deals" id="link-deals" style="top: 10px; left: 400px; width: 80px; height: 30px;">Deals</a>
        </nav>
      </header>

      <main role="main" id="main-content" style="top: 70px; left: 0px; width: 1000px; height: 600px;">
        <form role="search" id="flight-search-form" style="top: 80px; left: 10px; width: 800px; height: 100px;">
          <label for="input-origin">From</label>
          <input type="text" id="input-origin" name="origin" value="SFO" style="top: 90px; left: 10px; width: 100px; height: 30px;" />

          <label for="input-dest">To</label>
          <input type="text" id="input-dest" name="dest" value="JFK" style="top: 90px; left: 120px; width: 100px; height: 30px;" />

          <label for="input-pass">Account Password</label>
          <input type="password" id="input-pass" name="userPassword" value="super_secret_123" style="top: 90px; left: 240px; width: 100px; height: 30px;" />

          <button type="submit" id="btn-submit-search" style="top: 90px; left: 360px; width: 120px; height: 30px;">Search Flights</button>
        </form>

        <!-- Media elements -->
        <canvas id="flight-radar-chart" width="400" height="200" style="top: 200px; left: 50px; width: 400px; height: 200px;" aria-label="Route Radar Chart"></canvas>
        <svg id="carrier-logo" width="100" height="50" style="top: 200px; left: 500px; width: 100px; height: 50px;" role="img" aria-label="Airline Logo"></svg>
        <img id="promo-banner" src="https://example.com/banner.jpg" alt="Summer Discounts" width="300" height="150" style="top: 260px; left: 500px; width: 300px; height: 150px;" />
        <video id="safety-video" width="320" height="240" style="top: 420px; left: 500px; width: 320px; height: 240px;" controls></video>

        <!-- Overlapping elements with z-index stacking -->
        <div id="stack-container" style="top: 450px; left: 50px; width: 200px; height: 200px;">
          <button id="btn-stack-base" style="top: 460px; left: 60px; width: 100px; height: 50px; z-index: 10;">Base Button</button>
        </div>

        <!-- Dialog overlay -->
        <dialog id="booking-modal" role="dialog" aria-label="Confirm Booking" style="position: fixed; top: 100px; left: 200px; width: 600px; height: 400px; z-index: 500;">
          <h2>Confirm Flight Selection</h2>
          <button type="button" id="btn-confirm-modal" style="top: 300px; left: 250px; width: 100px; height: 40px;">Confirm</button>
          <button type="button" id="btn-cancel-modal" style="top: 300px; left: 370px; width: 100px; height: 40px;">Cancel</button>
        </dialog>
      </main>

      <aside role="complementary" id="site-sidebar" style="top: 700px; left: 0px; width: 1000px; height: 100px;">
        <h3>Recent Searches</h3>
      </aside>

      <footer role="contentinfo" id="site-footer" style="top: 800px; left: 0px; width: 1000px; height: 80px;">
        <p>© 2026 MATRIOSHAI Airlines</p>
      </footer>
    `;
  });

  it('generates a complete VisualPageModel correlated with DOM and screenshot metadata', () => {
    const model = visualEngine.generateVisualModel(101, { width: 1000, height: 800 }, 'STANDARD');

    expect(model.tab_id).toBe(101);
    expect(model.visual_model_id).toMatch(/^vis_mod_/);
    expect(model.visual_version).toBe(1);
    expect(model.is_stale).toBe(false);

    // Screenshot metadata
    expect(model.screenshot.id).toMatch(/^screen_/);
    expect(model.screenshot.width).toBe(1000);
    expect(model.screenshot.height).toBe(800);
    expect(model.screenshot.privacy_mode).toBe('STANDARD');

    // Visual regions
    expect(model.regions.length).toBeGreaterThanOrEqual(4);
    expect(model.regions.some((r) => r.type === 'HEADER')).toBe(true);
    expect(model.regions.some((r) => r.type === 'MAIN')).toBe(true);
    expect(model.regions.some((r) => r.type === 'FOOTER')).toBe(true);

    // Overlays & Dialogs
    expect(model.overlays.length).toBeGreaterThanOrEqual(1);
    expect(model.overlays[0].type).toBe('dialog');

    // Media & Visual Elements
    expect(model.visual_elements.some((v) => v.type === 'CANVAS')).toBe(true);
    expect(model.visual_elements.some((v) => v.type === 'IMAGE')).toBe(true);
    expect(model.visual_elements.some((v) => v.type === 'VIDEO')).toBe(true);
    expect(model.visual_elements.some((v) => v.type === 'BUTTON')).toBe(true);

    // Fixed elements
    expect(model.fixed_elements.length).toBeGreaterThanOrEqual(1);
  });

  it('identifies sensitive password fields for STRICT mode redaction', () => {
    const sensitiveBoxes = visualRedactor.findSensitiveBoxes();
    expect(sensitiveBoxes.length).toBeGreaterThanOrEqual(1);

    const strictModel = visualEngine.generateVisualModel(101, { width: 1000, height: 800 }, 'STRICT');
    expect(strictModel.privacy_mode).toBe('STRICT');
    expect(strictModel.metadata.sensitive_redacted_count).toBeGreaterThanOrEqual(1);
  });

  it('queries visual elements by type, region, and interactive filter', () => {
    const model = visualEngine.generateVisualModel(101, { width: 1000, height: 800 });

    // 1. Query all BUTTON elements
    const buttonQuery = visualQueryEngine.query(model, { type: 'BUTTON' });
    expect(buttonQuery.status).toBe('FOUND');
    expect(buttonQuery.elements.length).toBeGreaterThanOrEqual(2);

    // 2. Query all CANVAS elements
    const canvasQuery = visualQueryEngine.query(model, { type: 'CANVAS' });
    expect(canvasQuery.status).toBe('FOUND');
    expect(canvasQuery.elements.length).toBe(1);
    expect(canvasQuery.elements[0].is_canvas).toBe(true);

    // 3. Query interactive elements only
    const interactiveQuery = visualQueryEngine.query(model, { interactive_only: true });
    expect(interactiveQuery.elements.every((el) => el.is_interactive)).toBe(true);
  });

  it('executes point queries and sorts candidate elements by z-index stacking', () => {
    const model = visualEngine.generateVisualModel(101, { width: 1000, height: 800 });

    // Point query over the button inside #stack-container (at x=100, y=480)
    const ptResult = visualQueryEngine.queryPoint(model, 100, 480, 'DOM_VIEWPORT');

    expect(ptResult.status).toBe('FOUND');
    expect(ptResult.candidates.length).toBeGreaterThanOrEqual(1);
    expect(ptResult.topmost_element?.attributes.id).toBe('btn-stack-base');
  });

  it('marks visual page models as stale on invalidation', () => {
    const model = visualEngine.generateVisualModel(101, { width: 1000, height: 800 });
    expect(model.is_stale).toBe(false);

    visualEngine.invalidateModel();
    expect(model.is_stale).toBe(true);

    // Query on stale model
    const queryRes = visualQueryEngine.query(model, { type: 'BUTTON' });
    expect(queryRes.status).toBe('STALE');
  });
});
