import { describe, it, expect, vi, beforeEach } from "vitest";
import { BrowserAgentHarness } from "../agentHarness";
import { nativeBrowserService } from "../../../../services/browser/nativeService";

describe("Autonomous Multi-Step Harness — Wikipedia Fact Finding Experiment", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("Executes 5 consecutive multi-step runs searching Wikipedia for Rust creator and development start date", async () => {
    const harness = BrowserAgentHarness.getInstance();

    let currentStep = 0;
    let runsCompleted = 0;
    const runLogs: Array<{ run: number; steps: number; success: boolean; answer: string; trace: string[] }> = [];

    for (let run = 1; run <= 5; run++) {
      currentStep = 0;
      const trace: string[] = [];
      let finalExtractedFact = "";
      let stepCount = 0;
      const MAX_STEPS = 8;
      let runSuccess = false;

      // Mock inspectPage dynamic DOM states
      vi.spyOn(nativeBrowserService, "inspectPage").mockImplementation(async () => {
        if (currentStep === 0) {
          // Page 1: Wikipedia Search / Home
          return {
            schema_version: "1.0",
            page_id: "page_wiki_home",
            page_version: 1,
            tab_id: "tab_test",
            url: "https://en.wikipedia.org/wiki/Main_Page",
            origin: "https://en.wikipedia.org",
            title: "Wikipedia, the free encyclopedia",
            page_type: "ARTICLE",
            headings: ["Wikipedia, the free encyclopedia"],
            text_blocks: ["Welcome to Wikipedia, the free encyclopedia that anyone can edit."],
            interactive_elements: [
              {
                element_id: "el_search_input",
                role: "input",
                name: "Search Wikipedia",
                tag: "input",
                selector: "input[name='search']",
                sensitive: false,
                visible: true,
              },
              {
                element_id: "el_search_btn",
                role: "button",
                name: "Search",
                tag: "button",
                selector: "button.searchButton",
                sensitive: false,
                visible: true,
              },
            ],
            forms_count: 1,
            tables_count: 0,
            links_count: 25,
            trust_level: "untrusted",
            timestamp: new Date().toISOString(),
          };
        } else if (currentStep === 1) {
          // Page 2: Wikipedia Search Results for 'Rust programming language'
          return {
            schema_version: "1.0",
            page_id: "page_wiki_search",
            page_version: 2,
            tab_id: "tab_test",
            url: "https://en.wikipedia.org/w/index.php?search=Rust+programming+language",
            origin: "https://en.wikipedia.org",
            title: "Rust programming language - Search results - Wikipedia",
            page_type: "SEARCH",
            headings: ["Search results", "Rust (programming language)"],
            text_blocks: ["Rust is a general-purpose programming language emphasizing performance, type safety, and concurrency."],
            interactive_elements: [
              {
                element_id: "el_0",
                role: "link",
                name: "Rust (programming language) - Wikipedia article",
                tag: "a",
                href: "https://en.wikipedia.org/wiki/Rust_(programming_language)",
                selector: "[data-matrioshai-id='el_0']",
                sensitive: false,
                visible: true,
              },
              {
                element_id: "el_1",
                role: "link",
                name: "Rust (video game) - Wikipedia article",
                tag: "a",
                href: "https://en.wikipedia.org/wiki/Rust_(video_game)",
                selector: "[data-matrioshai-id='el_1']",
                sensitive: false,
                visible: true,
              },
            ],
            forms_count: 1,
            tables_count: 0,
            links_count: 30,
            trust_level: "untrusted",
            timestamp: new Date().toISOString(),
          };
        } else {
          // Page 3: 'Rust (programming language)' Article Page
          return {
            schema_version: "1.0",
            page_id: "page_rust_article",
            page_version: 3,
            tab_id: "tab_test",
            url: "https://en.wikipedia.org/wiki/Rust_(programming_language)",
            origin: "https://en.wikipedia.org",
            title: "Rust (programming language) - Wikipedia",
            page_type: "ARTICLE",
            headings: [
              "Rust (programming language)",
              "History",
              "Design and Features",
              "Syntax",
              "Ecosystem",
            ],
            text_blocks: [
              "The language grew out of a personal project begun in 2006 by Mozilla employee Graydon Hoare.",
              "Mozilla began sponsoring the project in 2009 and announced it in 2010.",
              "The first numbered pre-alpha release of the Rust compiler appeared in January 2012.",
            ],
            interactive_elements: [
              {
                element_id: "el_toc_history",
                role: "link",
                name: "History section",
                tag: "a",
                href: "#History",
                selector: "a[href='#History']",
                sensitive: false,
                visible: true,
              },
              {
                element_id: "el_graydon",
                role: "link",
                name: "Graydon Hoare",
                tag: "a",
                href: "https://en.wikipedia.org/wiki/Graydon_Hoare",
                selector: "a[title='Graydon Hoare']",
                sensitive: false,
                visible: true,
              },
            ],
            forms_count: 1,
            tables_count: 2,
            links_count: 120,
            trust_level: "untrusted",
            timestamp: new Date().toISOString(),
          };
        }
      });

      vi.spyOn(nativeBrowserService, "executeAIAction").mockImplementation(async (_tabId, action, target) => {
        if (action === "TYPE") {
          currentStep = 1;
          return {
            success: true,
            action: "TYPE",
            tab_id: "tab_test",
            risk_level: "Medium",
            approval_required: false,
            message: `Typed 'Rust programming language' into search input`,
          };
        } else if (action === "CLICK") {
          if (target === "el_0") {
            currentStep = 2;
            return {
              success: true,
              action: "CLICK",
              tab_id: "tab_test",
              risk_level: "Medium",
              approval_required: false,
              message: `Navigated to Rust (programming language) Wikipedia article`,
            };
          }
          return {
            success: true,
            action: "CLICK",
            tab_id: "tab_test",
            risk_level: "Medium",
            approval_required: false,
            message: `Clicked element ${target}`,
          };
        }
        return {
          success: true,
          action,
          tab_id: "tab_test",
          risk_level: "Low",
          approval_required: false,
          message: "Action executed",
        };
      });

      // Execute Autonomous Steps up to hard cap MAX_STEPS (8)
      while (stepCount < MAX_STEPS && !runSuccess) {
        stepCount++;
        // 1. Fresh Live DOM Observation
        const obs = await harness.observePage("tab_test");
        trace.push(`[Run ${run} | Step ${stepCount}] Observing URL: ${obs.url} (Title: '${obs.title}')`);

        if (obs.url.includes("Main_Page")) {
          // Action: Type search query
          const target = harness.resolveTarget("Search Wikipedia", obs);
          expect(target).not.toBeNull();
          const val = harness.validateAction("TYPE", target!, obs);
          expect(val.valid).toBe(true);
          await harness.executeAction("tab_test", "TYPE", target, "Rust programming language");
          trace.push(`[Run ${run} | Step ${stepCount}] Action: Typed 'Rust programming language' into search box.`);
        } else if (obs.url.includes("search=Rust")) {
          // Action: Click 1st organic search result
          const target = harness.resolveTarget({ ordinal: 1 }, obs);
          expect(target).not.toBeNull();
          const val = harness.validateAction("CLICK", target!, obs);
          expect(val.valid).toBe(true);
          await harness.executeAction("tab_test", "CLICK", target);
          trace.push(`[Run ${run} | Step ${stepCount}] Action: Clicked 1st search result ('${target?.text}')`);
        } else if (obs.url.includes("Rust_(programming_language)")) {
          // Action: Locate 'History' and extract creator & development start date
          const historyText = obs.sections.find((s) => s.toLowerCase().includes("history")) || "History";
          trace.push(`[Run ${run} | Step ${stepCount}] Section Found: '${historyText}'`);
          
          // Verify section & extract facts from structured text blocks
          const sem = await nativeBrowserService.inspectPage("tab_test");
          const targetBlock = (sem.text_blocks || []).find((b) => b.includes("Graydon Hoare") || b.includes("2006"));
          
          if (targetBlock) {
            finalExtractedFact = targetBlock;
            trace.push(`[Run ${run} | Step ${stepCount}] Extracted Fact: "${targetBlock}"`);
            runSuccess = true;
          }
        }
      }

      runLogs.push({
        run,
        steps: stepCount,
        success: runSuccess,
        answer: finalExtractedFact,
        trace,
      });

      if (runSuccess) runsCompleted++;
    }

    // Verify all 5 runs succeeded within hard cap
    expect(runsCompleted).toBe(5);
    runLogs.forEach((log) => {
      expect(log.success).toBe(true);
      expect(log.steps).toBeLessThanOrEqual(8);
      expect(log.answer).toContain("2006");
      expect(log.answer).toContain("Graydon Hoare");
    });

    console.log("=== MULTI-STEP AUTONOMOUS HARNESS SUMMARY (5 RUNS) ===");
    console.log(`Success Rate: ${runsCompleted}/5 (100%)`);
    console.log(`Average Steps Per Run: ${(runLogs.reduce((acc, l) => acc + l.steps, 0) / 5).toFixed(1)}`);
    console.log(`Extracted Fact: "${runLogs[0].answer}"`);
  });
});
