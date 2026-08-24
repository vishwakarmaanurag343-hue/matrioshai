// @vitest-environment happy-dom
import { describe, it, expect, beforeEach } from 'vitest';
import { PageObservationEngine } from '../content/observation-engine';

describe('MATRIOSHAI Page Observation Engine (Phase 4)', () => {
  let engine: PageObservationEngine;

  beforeEach(() => {
    engine = new PageObservationEngine();
    document.body.innerHTML = `
      <header role="banner">
        <h1 id="main-title">Test Wikipedia Article</h1>
        <nav role="navigation">
          <a href="https://example.com/home" id="link-home">Home</a>
          <a href="https://example.com/about" id="link-about">About Us</a>
        </nav>
      </header>
      <main role="main">
        <h2>History Section</h2>
        <p>The verification code for this test is XQ-4471-ZETA.</p>
        <p>Rust is a multi-paradigm, general-purpose programming language designed for performance and safety.</p>
        
        <form id="search-form">
          <label for="search-input">Search query</label>
          <input type="text" id="search-input" name="search" placeholder="Search here..." value="Rust programming" />
          
          <label for="pass-input">Password</label>
          <input type="password" id="pass-input" value="secret_pass_123" />
          
          <button type="submit" id="btn-submit">Search</button>
          <button type="button" disabled id="btn-disabled">Disabled Action</button>
        </form>
      </main>
      <footer role="contentinfo">
        <p>© 2026 Test Page</p>
      </footer>
    `;
  });

  it('extracts complete structured PageObservation', () => {
    const obs = engine.extractPageObservation(101);

    expect(obs.tab_id).toBe(101);
    expect(obs.observation_id).toMatch(/^obs_/);
    expect(obs.viewport).toBeDefined();
    expect(obs.viewport.width).toBeGreaterThanOrEqual(0);

    // Visible text extraction
    expect(obs.visible_text.some((t) => t.includes('XQ-4471-ZETA'))).toBe(true);
    expect(obs.visible_text.some((t) => t.includes('Rust is a multi-paradigm'))).toBe(true);

    // Headings extraction
    expect(obs.headings.length).toBe(2);
    expect(obs.headings[0]).toEqual({ level: 1, text: 'Test Wikipedia Article', id: 'main-title' });
    expect(obs.headings[1]).toEqual({ level: 2, text: 'History Section', id: null });

    // Landmarks extraction
    expect(obs.landmarks.some((l) => l.role === 'banner')).toBe(true);
    expect(obs.landmarks.some((l) => l.role === 'main')).toBe(true);

    // Interactive elements extraction
    expect(obs.interactive_elements.length).toBeGreaterThanOrEqual(4);

    const homeLink = obs.interactive_elements.find((el) => el.attributes.id === 'link-home');
    expect(homeLink).toBeDefined();
    expect(homeLink?.tag_name).toBe('a');
    expect(homeLink?.href).toBe('https://example.com/home');
    expect(homeLink?.element_id).toMatch(/^el_/);

    const searchInput = obs.interactive_elements.find((el) => el.attributes.id === 'search-input');
    expect(searchInput).toBeDefined();
    expect(searchInput?.tag_name).toBe('input');
    expect(searchInput?.value).toBe('Rust programming');
    expect(searchInput?.placeholder).toBe('Search here...');

    const passInput = obs.interactive_elements.find((el) => el.attributes.id === 'pass-input');
    expect(passInput).toBeDefined();
    expect(passInput?.value).toBe('[MASKED_PASSWORD]'); // Sensitive password masking

    const submitBtn = obs.interactive_elements.find((el) => el.attributes.id === 'btn-submit');
    expect(submitBtn).toBeDefined();
    expect(submitBtn?.is_enabled).toBe(true);

    const disabledBtn = obs.interactive_elements.find((el) => el.attributes.id === 'btn-disabled');
    expect(disabledBtn).toBeDefined();
    expect(disabledBtn?.is_enabled).toBe(false);
  });
});
