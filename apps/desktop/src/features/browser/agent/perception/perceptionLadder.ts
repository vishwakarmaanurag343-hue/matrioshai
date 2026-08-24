import { nativeBrowserService } from "../../../../services/browser/nativeService";
import { PageModel, PageModelBuilder } from "./pageModel";
import { PerceptionLevel, PerceptionSnapshot } from "../types";

/**
 * UNIVERSAL PERCEPTION FALLBACK LADDER.
 *
 * When the primary DOM extraction yields an empty/unusable observation the
 * ladder escalates automatically — no website-specific selectors anywhere:
 *
 *   L1 dom            — semantic DOM extraction (browser_inspect_page)
 *   L2 semantic-tree  — accessibility/semantic page command (browser_get_semantic_page)
 *   L3 rendered-text  — universal rendered-text+geometry probe via debug eval
 *                       (traverses open shadow roots and same-origin iframes)
 *   L4 visual         — screenshot perception (only if a capture command exists)
 *   L5 alternative-route — NOT here: route changes are reasoning decisions
 *                          informed by the failed-strategies feedback.
 */

export interface PerceptionResult {
  model: PageModel;
  level: PerceptionLevel;
  degraded: boolean;      // true if L1 failed and we fell back
  note: string;           // truthful description for the reasoner + events
}

/** A page is observation-empty when it offers nothing to reason about. */
export function isObservationEmpty(model: PageModel): boolean {
  const blank = !model.url || model.url.startsWith("about:blank") || model.url.includes("matrioshai.local");
  if (blank) return false; // genuinely blank tab is truthfully reported as-is
  return (
    model.links.length === 0 &&
    model.buttons.length === 0 &&
    model.inputs.length === 0 &&
    model.sections.length === 0 &&
    (model.textBlocks?.length ?? 0) === 0
  );
}

/** Universal rendered-text probe: no selectors beyond plain HTML semantics. */
const RENDERED_TEXT_JS = `(() => {
  const collect = (root, out) => {
    try {
      root.querySelectorAll('a[href],button,input,select,textarea,[role=link],[role=button],[role=searchbox],[role=textbox]').forEach(el => {
        if (out.links.length >= 40) return;
        const tag = (el.tagName||'').toLowerCase();
        const name = ((el.innerText||el.value||el.getAttribute('aria-label')||'')+'').trim().slice(0,80);
        const rect = el.getBoundingClientRect();
        if (!name && tag !== 'input') return;
        if (rect.width === 0 && rect.height === 0 && tag !== 'input') return;
        out.links.push({
          element_id: 'rt_' + out.links.length,
          role: tag === 'a' ? 'link' : tag === 'input' || tag === 'textarea' ? 'textbox' : 'button',
          tag, name,
          href: (el.href || el.getAttribute('href') || '') + '',
          selector: '', value: (el.value||'')+'', placeholder: (el.placeholder||'')+'',
          aria_label: (el.getAttribute('aria-label')||'')+'',
          input_type: (el.type||'')+'', sensitive: (el.type==='password'),
          visible: true,
        });
      });
      root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) collect(el.shadowRoot, out); });
    } catch (e) {}
  };
  const out = { headings: [], texts: [], links: [] };
  try {
    document.querySelectorAll('h1,h2,h3').forEach(h => { if (out.headings.length < 10) out.headings.push((h.innerText||'').trim().slice(0,160)); });
    document.querySelectorAll('p,span,div').forEach(el => {
      if (out.texts.length >= 18) return;
      const t = ((el.innerText)||'').trim();
      // Long prose blocks plus SHORT price/fact snippets (e.g. ₹1,299) —
      // commerce data lives in tiny nodes the prose filter used to drop.
      const isFact = /^(?:₹|rs\.?\s|\$\s?|€\s?|£\s?)\d[\d,.]*%?$|^\d[\d,.]*\s?(?:off|%)$/i.test(t);
      const longEnough = (t.length > 60 && t.length < 400) || (isFact && t.length >= 3 && t.length <= 48);
      if (longEnough && !out.texts.some(x => x.includes(t) || t.startsWith(x))) out.texts.push(t.slice(0,280));
    });
    collect(document, out);
    document.querySelectorAll('iframe').forEach(f => { try { if (f.contentDocument) collect(f.contentDocument, out); } catch(e) {} });
  } catch (e) {}
  return JSON.stringify(out);
})()`;

export class PerceptionLadder {
  /**
   * Observe a tab, escalating levels until something usable comes back.
   * Never throws — returns the best-available (possibly empty) model with a
   * truthful note so the loop can diagnose instead of crash.
   */
  static async observe(tabId: string): Promise<PerceptionResult> {
    // ---------- L1: semantic DOM ----------
    try {
      const sem = await nativeBrowserService.inspectPage(tabId);
      const snapshot = this.toSnapshot(sem);
      const model = PageModelBuilder.build(snapshot);
      if (!isObservationEmpty(model)) {
        return { model, level: "dom", degraded: false, note: "" };
      }
    } catch { /* fall through */ }

    // ---------- L2: accessibility / semantic tree ----------
    try {
      const sem = await nativeBrowserService.getSemanticPage(tabId);
      const snapshot = this.toSnapshot(sem);
      const model = PageModelBuilder.build(snapshot);
      if (!isObservationEmpty(model)) {
        return { model, level: "semantic-tree", degraded: true, note: "DOM extraction was empty; used accessibility/semantic tree." };
      }
    } catch { /* fall through */ }

    // ---------- L3/L4: rendered text + geometry (shadow DOM / iframe aware) ----------
    try {
      const dbg = await nativeBrowserService.debugEval(tabId, RENDERED_TEXT_JS);
      if (dbg && dbg.custom_js_result) {
        const parsed = JSON.parse(dbg.custom_js_result);
        const snapshot = {
          url: dbg.url || "",
          title: dbg.title || "",
          headings: parsed.headings || [],
          text_blocks: parsed.texts || [],
          interactive_elements: parsed.links || [],
          forms_count: 0,
          tables_count: 0,
          links_count: (parsed.links || []).length,
          timestamp: new Date().toISOString(),
          observation_failed: false,
          observation_status: "OBSERVATION_RENDERED_TEXT_FALLBACK",
        };
        const model = PageModelBuilder.build(snapshot);
        if (!isObservationEmpty(model)) {
          return { model, level: "rendered-text", degraded: true, note: "DOM and semantic extraction were empty; used rendered text/geometry probe (shadow DOM + iframe traversal)." };
        }
      }
    } catch { /* fall through */ }

    // ---------- L5: visual perception ----------
    // No screenshot-perception command exists in the Rust runtime yet; report
    // honestly rather than pretend. The reasoner sees this and can choose an
    // alternative discovery route (L6) itself.
    try {
      const sem = await nativeBrowserService.inspectPage(tabId);
      const model = PageModelBuilder.build(this.toSnapshot(sem));
      return {
        model,
        level: "visual",
        degraded: true,
        note: "All structural perception levels returned empty; screenshot perception not yet available. An alternative discovery route is required.",
      };
    } catch {
      return {
        model: PageModelBuilder.build({
          url: "", title: "", headings: [], text_blocks: [], interactive_elements: [],
          forms_count: 0, tables_count: 0, links_count: 0,
          timestamp: new Date().toISOString(),
          observation_failed: true, observation_status: "OBSERVATION_FAILED_ALL_LEVELS",
        }),
        level: "visual",
        degraded: true,
        note: "Observation completely unavailable on this tab.",
      };
    }
  }

  private static toSnapshot(sem: any): PerceptionSnapshot {
    return {
      url: sem.url || "",
      title: sem.title || "",
      headings: sem.headings || [],
      text_blocks: sem.text_blocks || [],
      interactive_elements: (sem.interactive_elements || []).map((e: any) => ({
        id: e.element_id,
        name: e.name,
        role: e.role,
        tag: e.tag || e.role,
        text: e.name,
        href: e.href,
        selector: e.selector,
        sensitive: e.sensitive,
        boundingBox: e.rect,
        visible: e.visible !== false,
        value: (e as any).value,
        placeholder: (e as any).placeholder,
        ariaLabel: (e as any).aria_label,
        inputType: (e as any).input_type,
        disabled: !!(e as any).disabled,
        enabled: (e as any).enabled !== false && !(e as any).disabled,
      })),
      forms_count: sem.forms_count || 0,
      tables_count: sem.tables_count || 0,
      links_count: sem.links_count || 0,
      timestamp: new Date().toISOString(),
      observation_failed: sem.observation_failed ?? false,
      observation_status: sem.observation_status || "OBSERVATION_SUCCESS",
    };
  }
}
