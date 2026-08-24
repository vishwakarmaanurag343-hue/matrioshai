// @vitest-environment happy-dom
import { describe, it, expect, beforeEach } from 'vitest';
import { SemanticPageAnalyzer } from '../content/semantic-analyzer';
import { SemanticQueryEngine } from '../content/semantic-query-engine';

describe('MATRIOSHAI Semantic Page & Accessibility Intelligence (Phase 5)', () => {
  let analyzer: SemanticPageAnalyzer;
  let queryEngine: SemanticQueryEngine;

  beforeEach(() => {
    analyzer = new SemanticPageAnalyzer();
    queryEngine = new SemanticQueryEngine();

    document.body.innerHTML = `
      <header role="banner">
        <h1 id="page-heading">Flight Search & Booking</h1>
        <nav role="navigation">
          <a href="https://example.com/flights" id="nav-flights">Flights</a>
          <a href="https://example.com/hotels" id="nav-hotels">Hotels</a>
        </nav>
      </header>

      <main role="main">
        <div role="tablist" id="main-tabs">
          <button role="tab" aria-selected="true" aria-controls="panel-flights" id="tab-flights">Flights</button>
          <button role="tab" aria-selected="false" aria-controls="panel-hotels" id="tab-hotels">Hotels</button>
        </div>

        <form id="flight-search-form" name="flightSearch" method="POST" action="/search">
          <h2>Search Flights</h2>
          
          <label for="input-from">From</label>
          <input type="text" id="input-from" name="from" placeholder="Origin airport" value="SFO" required />

          <label for="input-to">To</label>
          <input type="text" id="input-to" name="to" placeholder="Destination airport" value="JFK" required />

          <label for="input-departure">Departure</label>
          <input type="date" id="input-departure" name="departureDate" value="2026-09-01" />

          <label for="input-return">Return</label>
          <input type="date" id="input-return" name="returnDate" value="2026-09-10" />

          <label for="pass-field">Password (Secret)</label>
          <input type="password" id="pass-field" name="userPassword" value="super_secret_12345" />

          <fieldset id="cabin-class-fieldset">
            <legend>Cabin class</legend>
            <label><input type="radio" name="cabinClass" value="economy" checked id="radio-eco" /> Economy</label>
            <label><input type="radio" name="cabinClass" value="business" id="radio-biz" /> Business</label>
            <label><input type="radio" name="cabinClass" value="first" id="radio-first" /> First</label>
          </fieldset>

          <label><input type="checkbox" id="chk-nonstop" name="nonstop" checked /> Non-stop only</label>

          <!-- Labelledby button -->
          <span id="btn-lbl">Search flights</span>
          <button type="submit" id="btn-search-main" aria-labelledby="btn-lbl">Submit</button>

          <!-- Disabled button -->
          <button type="button" disabled id="btn-disabled-save">Save Search</button>
        </form>

        <!-- Duplicate buttons to test ambiguity detection -->
        <div id="duplicate-actions">
          <button class="action-btn" id="btn-dup-1">Search</button>
          <button class="action-btn" id="btn-dup-2">Search</button>
          <button class="action-btn" id="btn-dup-3">Search</button>
        </div>

        <!-- Table -->
        <table id="results-table" aria-label="Available Flights">
          <thead>
            <tr><th>Airline</th><th>Departure</th><th>Price</th></tr>
          </thead>
          <tbody>
            <tr><td>Air India</td><td>10:00</td><td>$500</td></tr>
            <tr><td>IndiGo</td><td>14:00</td><td>$420</td></tr>
          </tbody>
        </table>

        <!-- List -->
        <ul id="features-list" aria-label="Flight Amenities">
          <li>Free Wi-Fi</li>
          <li>Complimentary Meals</li>
        </ul>

        <!-- Dialog -->
        <dialog id="fare-dialog" aria-label="Fare Rules">
          <h3>Fare Rules & Restrictions</h3>
          <button type="button" id="btn-close-dialog">Close</button>
        </dialog>
      </main>
    `;
  });

  it('generates a complete SemanticPageModel with accessibility semantics', () => {
    const model = analyzer.analyzePage(101);

    expect(model.tab_id).toBe(101);
    expect(model.semantic_model_id).toMatch(/^sem_/);
    expect(model.model_version).toBe(1);
    expect(model.is_stale).toBe(false);

    // Headings
    expect(model.headings.length).toBeGreaterThanOrEqual(2);
    expect(model.headings[0].text).toBe('Flight Search & Booking');
    expect(model.headings[0].level).toBe(1);

    // Landmarks
    expect(model.landmarks.some((l) => l.role === 'banner')).toBe(true);
    expect(model.landmarks.some((l) => l.role === 'main')).toBe(true);

    // Forms
    expect(model.forms.length).toBe(1);
    expect(model.forms[0].form_id).toBe('flight-search-form');
    expect(model.forms[0].required_field_ids.length).toBeGreaterThanOrEqual(2);

    // Radio Groups
    expect(model.radio_groups.length).toBe(1);
    expect(model.radio_groups[0].group_name).toBe('cabinClass');
    expect(model.radio_groups[0].label).toBe('Cabin class');
    expect(model.radio_groups[0].options.length).toBe(3);
    expect(model.radio_groups[0].selected_element_id).toBeDefined();

    // Tabs
    expect(model.tabs.length).toBe(1);
    expect(model.tabs[0].tabs.length).toBe(2);
    expect(model.tabs[0].tabs[0].name).toBe('Flights');
    expect(model.tabs[0].tabs[0].selected).toBe(true);

    // Tables
    expect(model.tables.length).toBe(1);
    expect(model.tables[0].headers).toEqual(['Airline', 'Departure', 'Price']);
    expect(model.tables[0].rows.length).toBe(2);

    // Lists
    expect(model.lists.length).toBe(1);
    expect(model.lists[0].items).toEqual(['Free Wi-Fi', 'Complimentary Meals']);

    // Dialogs
    expect(model.dialogs.length).toBe(1);
    expect(model.dialogs[0].name).toBe('Fare Rules');
  });

  it('resolves accessible names using label-for and aria-labelledby', () => {
    const model = analyzer.analyzePage(101);

    // label for="input-from" -> name="From"
    const fromEl = model.interactive_elements.find((el) => el.attributes.id === 'input-from');
    expect(fromEl).toBeDefined();
    expect(fromEl?.name).toBe('From');
    expect(fromEl?.role).toBe('textbox');
    expect(fromEl?.semantic_type).toBe('TEXT');

    // label for="input-departure" -> name="Departure"
    const depEl = model.interactive_elements.find((el) => el.attributes.id === 'input-departure');
    expect(depEl).toBeDefined();
    expect(depEl?.name).toBe('Departure');
    expect(depEl?.semantic_type).toBe('DATE');

    // aria-labelledby="btn-lbl" -> name="Search flights"
    const searchBtn = model.interactive_elements.find((el) => el.attributes.id === 'btn-search-main');
    expect(searchBtn).toBeDefined();
    expect(searchBtn?.name).toBe('Search flights');
    expect(searchBtn?.role).toBe('button');
  });

  it('protects sensitive password fields and masks values', () => {
    const model = analyzer.analyzePage(101);
    const passEl = model.interactive_elements.find((el) => el.attributes.id === 'pass-field');

    expect(passEl).toBeDefined();
    expect(passEl?.sensitive).toBe(true);
    expect(passEl?.value_available).toBe(false);
    expect(passEl?.value_preview).toBeNull();
  });

  it('queries uniquely by label or accessible name (FOUND)', () => {
    const model = analyzer.analyzePage(101);

    // 1. Query by label "Departure"
    const resDep = queryEngine.query(model, { label: 'Departure' });
    expect(resDep.status).toBe('FOUND');
    expect(resDep.element?.name).toBe('Departure');
    expect(resDep.element?.semantic_type).toBe('DATE');

    // 2. Query by role="button" and name="Search flights"
    const resBtn = queryEngine.query(model, { role: 'button', name: 'Search flights' });
    expect(resBtn.status).toBe('FOUND');
    expect(resBtn.element?.attributes.id).toBe('btn-search-main');
  });

  it('detects ambiguity on duplicate button names and never silently picks (AMBIGUOUS)', () => {
    const model = analyzer.analyzePage(101);

    // Query for "Search" button where 3 identical buttons exist
    const res = queryEngine.query(model, { role: 'button', name: 'Search' });

    expect(res.status).toBe('AMBIGUOUS');
    expect(res.matches.length).toBe(3);
    expect(res.element).toBeUndefined(); // Crucial: Never arbitrarily select one
  });

  it('detects disabled element states correctly', () => {
    const model = analyzer.analyzePage(101);
    const disabledEl = model.interactive_elements.find((el) => el.attributes.id === 'btn-disabled-save');

    expect(disabledEl).toBeDefined();
    expect(disabledEl?.enabled).toBe(false);
  });

  it('detects stale model references after invalidation', () => {
    const model = analyzer.analyzePage(101);
    const fromEl = model.interactive_elements.find((el) => el.attributes.id === 'input-from')!;

    const ref = {
      semantic_model_id: model.semantic_model_id,
      observation_id: model.observation_id,
      element_id: fromEl.element_id,
      role: fromEl.role,
      name: fromEl.name,
      tag_name: fromEl.tag_name,
      stable_id: fromEl.attributes.id
    };

    // Valid resolution before staleness
    const resBefore = queryEngine.resolveElement(model, ref);
    expect(resBefore.status).toBe('FOUND');

    // Invalidate model
    analyzer.invalidateModel();

    // Resolution after staleness
    const resAfter = queryEngine.resolveElement(model, ref);
    expect(resAfter.status).toBe('STALE');
  });
});
