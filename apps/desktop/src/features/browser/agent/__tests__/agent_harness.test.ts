import { describe, it, expect } from "vitest";
import { PageModelBuilder } from "../perception/pageModel";
import { ElementResolver } from "../perception/elementResolver";
import { ActionVerifier } from "../execution/actionVerifier";
import { PerceptionSnapshot } from "../types";

describe("Browser Agent Execution Harness & Semantic Resolver", () => {
  const mockGoogleSearchSnapshot: PerceptionSnapshot = {
    url: "https://www.google.com/search?q=8th+pay+commission+news",
    title: "8th pay commission news - Google Search",
    headings: ["Search Query: 8th pay commission news", "Top stories", "People also ask"],
    text_blocks: [
      "Latest 8th Pay Commission updates and expected salary hike matrix for central government employees.",
      "Economic Times: 8th Pay Commission salary calculator and timeline.",
    ],
    interactive_elements: [
      {
        id: "el_ad_0",
        name: "Sponsored - Best Fixed Deposit Rates 2026",
        role: "link",
        tag: "a",
        text: "Sponsored - Best Fixed Deposit Rates 2026",
        href: "https://www.googleadservices.com/pagead/aclk?ad=123",
        selector: "a.ad-link",
      },
      {
        id: "el_0",
        name: "8th Pay Commission: Expected Date, Salary Hike & Fitment Factor - Zee Business",
        role: "link",
        tag: "a",
        text: "8th Pay Commission: Expected Date, Salary Hike & Fitment Factor - Zee Business",
        href: "https://www.zeebiz.com/personal-finance/8th-pay-commission-updates-1001",
        selector: "[data-matrioshai-id='el_0']",
      },
      {
        id: "el_1",
        name: "8th Pay Commission News: Government clarifies position on formation - NDTV",
        role: "link",
        tag: "a",
        text: "8th Pay Commission News: Government clarifies position on formation - NDTV",
        href: "https://www.ndtv.com/india-news/8th-pay-commission-formation-clarification-2002",
        selector: "[data-matrioshai-id='el_1']",
      },
      {
        id: "el_paa_0",
        name: "People also ask: When will 8th Pay Commission be implemented?",
        role: "link",
        tag: "a",
        text: "People also ask: When will 8th Pay Commission be implemented?",
        href: "https://www.google.com/search?q=related-question-1",
        selector: "a.related-question",
      },
      {
        id: "el_2",
        name: "8th Pay Commission salary calculator: Check Level 5–8 matrix - The Economic Times",
        role: "link",
        tag: "a",
        text: "8th Pay Commission salary calculator: Check Level 5–8 matrix - The Economic Times",
        href: "https://economictimes.indiatimes.com/wealth/personal-finance-news/8th-pay-commission-calculator-matrix/3003",
        selector: "[data-matrioshai-id='el_2']",
      },
      {
        id: "el_3",
        name: "Amazon.in: Books on 7th and 8th Pay Commission Rules",
        role: "link",
        tag: "a",
        text: "Amazon.in: Books on 7th and 8th Pay Commission Rules",
        href: "https://www.amazon.in/dp/B08PAYCOMM",
        selector: "[data-matrioshai-id='el_3']",
      },
      {
        id: "el_4",
        name: "8th Pay Commission Explained in 5 Minutes - YouTube",
        role: "link",
        tag: "a",
        text: "8th Pay Commission Explained in 5 Minutes - YouTube",
        href: "https://www.youtube.com/watch?v=paycomm888",
        selector: "[data-matrioshai-id='el_4']",
      },
    ],
    forms_count: 1,
    tables_count: 0,
    links_count: 7,
    timestamp: "2026-08-22T11:20:00Z",
  };

  it("Test 1: Normalizes search results and correctly filters Ads and People Also Ask", () => {
    const pageModel = PageModelBuilder.build(mockGoogleSearchSnapshot);

    expect(pageModel.searchResults.length).toBeGreaterThanOrEqual(4);
    expect(pageModel.advertisements.length).toBe(1);
    expect(pageModel.peopleAlsoAsk.length).toBe(1);

    const organic = pageModel.searchResults.filter((r) => r.isOrganic);
    expect(organic.length).toBe(5);
    expect(organic[0].index).toBe(1);
    expect(organic[1].index).toBe(2);
    expect(organic[2].index).toBe(3);
  });

  it("Test 2: Resolves 'open first website' to the first organic result (Zee Business)", () => {
    const pageModel = PageModelBuilder.build(mockGoogleSearchSnapshot);
    const resolved = ElementResolver.resolveOrdinal(1, pageModel.searchResults);

    expect(resolved).not.toBeNull();
    expect(resolved?.strategy).toBe("ordinal");
    expect(resolved?.element.id).toBe("el_0");
    expect(resolved?.href).toContain("zeebiz.com");
    expect(resolved?.confidence).toBeGreaterThanOrEqual(0.95);
  });

  it("Test 3: Resolves 'open second website' to the second organic result (NDTV)", () => {
    const pageModel = PageModelBuilder.build(mockGoogleSearchSnapshot);
    const resolved = ElementResolver.resolveOrdinal(2, pageModel.searchResults);

    expect(resolved).not.toBeNull();
    expect(resolved?.element.id).toBe("el_1");
    expect(resolved?.href).toContain("ndtv.com");
  });

  it("Test 4: Resolves 'open the 3rd website' to Economic Times without confusing ads/PAA", () => {
    const pageModel = PageModelBuilder.build(mockGoogleSearchSnapshot);
    const resolved = ElementResolver.resolveOrdinal(3, pageModel.searchResults);

    expect(resolved).not.toBeNull();
    expect(resolved?.element.id).toBe("el_2");
    expect(resolved?.href).toContain("economictimes.indiatimes.com");
    expect(resolved?.text).toContain("Economic Times");
  });

  it("Test 5: Resolves 'open the Economic Times result' by domain", () => {
    const pageModel = PageModelBuilder.build(mockGoogleSearchSnapshot);
    const resolved = ElementResolver.resolveByDomain("economictimes.indiatimes.com", pageModel.searchResults, pageModel.links);

    expect(resolved).not.toBeNull();
    expect(resolved?.element.id).toBe("el_2");
    expect(resolved?.strategy).toBe("domain");
    expect(resolved?.href).toContain("economictimes.indiatimes.com");
  });

  it("Test 6: Resolves 'open Amazon result' by domain query", () => {
    const pageModel = PageModelBuilder.build(mockGoogleSearchSnapshot);
    const resolved = ElementResolver.resolveByDomain("amazon.in", pageModel.searchResults, pageModel.links);

    expect(resolved).not.toBeNull();
    expect(resolved?.element.id).toBe("el_3");
    expect(resolved?.href).toContain("amazon.in");
  });

  it("Test 7: Resolves YouTube video result", () => {
    const pageModel = PageModelBuilder.build(mockGoogleSearchSnapshot);
    const resolved = ElementResolver.resolveByDomain("youtube.com", pageModel.searchResults, pageModel.links);

    expect(resolved).not.toBeNull();
    expect(resolved?.element.id).toBe("el_4");
    expect(resolved?.href).toContain("youtube.com");
  });

  it("Test 8: Resolves semantic text query using ElementResolver.resolveBestCandidate", () => {
    const pageModel = PageModelBuilder.build(mockGoogleSearchSnapshot);
    const resolved = ElementResolver.resolveBestCandidate({ text: "Salary calculator Level 5-8" }, pageModel);

    expect(resolved).not.toBeNull();
    expect(resolved?.element.id).toBe("el_2");
    expect(resolved?.href).toContain("economictimes.indiatimes.com");
  });

  it("Test 9: Fingerprint stability across observation updates", () => {
    const elem = mockGoogleSearchSnapshot.interactive_elements[1];
    const fp1 = ElementResolver.generateFingerprint(elem, "zeebiz.com");
    const fp2 = ElementResolver.generateFingerprint({ ...elem, id: "el_99" }, "zeebiz.com");

    // Fingerprint should be stable even if temporary ID el_0 shifts to el_99
    expect(fp1).toBe(fp2);
  });

  it("Test 10: ActionVerifier detects 404 / error pages and marks verification FAILED", () => {
    const beforeSnap: PerceptionSnapshot = {
      ...mockGoogleSearchSnapshot,
    };
    const errorPageSnap: PerceptionSnapshot = {
      url: "https://example.com/missing-article",
      title: "404 Not Found - Server Error",
      headings: ["404 Page Not Found"],
      text_blocks: ["The requested URL was not found on this server."],
      interactive_elements: [],
      forms_count: 0,
      tables_count: 0,
      links_count: 0,
      timestamp: "2026-08-22T11:21:00Z",
    };

    const verif = ActionVerifier.verifyTransition("CLICK", "el_0", beforeSnap, errorPageSnap);
    expect(verif.success).toBe(false);
    expect(verif.message).toContain("404");
  });

  it("Test 11: Resolves colloquial / typo request 'open the ebist and book for me' to top organic result", () => {
    const pageModel = PageModelBuilder.build(mockGoogleSearchSnapshot);
    const resolved = ElementResolver.resolveBestCandidate("open the ebist and book for me", pageModel);

    expect(resolved).not.toBeNull();
    expect(resolved?.element.id).toBe("el_0");
    expect(resolved?.strategy).toBe("ordinal");
    expect(resolved?.href).toContain("zeebiz.com");
  });
});
