import { PerceptionSnapshot, RobustElement } from "../types";

export interface SearchResult {
  index: number; // 1-indexed organic position (1st, 2nd, 3rd)
  title: string;
  href: string;
  visibleText: string;
  domain: string;
  position: number;
  boundingRect: { x: number; y: number; width: number; height: number };
  isOrganic: boolean;
  isAdvertisement: boolean;
  isVideo: boolean;
  isShopping: boolean;
  isNews: boolean;
  isPeopleAlsoAsk: boolean;
  elementReference: RobustElement;
  confidence: number;
}

export interface PageModel {
  url: string;
  title: string;
  sections: string[];
  textBlocks?: string[]; // rendered page text blocks (L1 DOM or L3 fallback)
  links: RobustElement[];
  buttons: RobustElement[];
  inputs: RobustElement[];
  selects: RobustElement[];
  searchResults: SearchResult[];
  advertisements: RobustElement[];
  peopleAlsoAsk: RobustElement[];
  videos: RobustElement[];
  formsCount: number;
  tablesCount: number;
  timestamp: string;
  observationFailed?: boolean;
  observationStatus?: string;
}

export interface SemanticTarget {
  semanticType?: "search-result" | "link" | "button" | "input" | "ordinal" | "domain" | "text";
  ordinal?: number; // e.g. 1, 2, 3 for 1st, 2nd, 3rd result
  text?: string;
  domain?: string;
  href?: string;
  role?: string;
  description?: string;
  constraints?: {
    excludeAds?: boolean;
    excludeVideos?: boolean;
    excludePeopleAlsoAsk?: boolean;
  };
}

export interface ResolvedElement {
  element: RobustElement;
  strategy: "ordinal" | "domain" | "text" | "href" | "role" | "fallback" | "direct_id";
  confidence: number;
  reason: string;
  href: string;
  text: string;
  role: string;
  boundingRect: { x: number; y: number; width: number; height: number };
  fingerprint: string;
}

export class PageModelBuilder {
  /**
   * True when a value read from an anchor's href is CSS-selector grammar
   * rather than a URL. Real URLs never carry raw whitespace or leading
   * selector tokens — browsers percent-encode those in the href property.
   */
  private static looksLikeSelectorNotUrl(href: string): boolean {
    if (!href) return false;
    return /^[.:\[]/.test(href) || /\s/.test(href) || /::|>|:has\(/.test(href);
  }

  /**
   * Builds a normalized semantic PageModel from a raw perception snapshot.
   */
  static build(snapshot: PerceptionSnapshot): PageModel {
    const url = snapshot.url || "";
    const isSearchEngine =
      url.includes("google.") ||
      url.includes("bing.") ||
      url.includes("duckduckgo.") ||
      url.includes("/search") ||
      url.includes("search=") ||
      url.includes("?q=") ||
      url.includes("wikipedia.org");

    const links: RobustElement[] = [];
    const buttons: RobustElement[] = [];
    const inputs: RobustElement[] = [];
    const selects: RobustElement[] = [];
    const advertisements: RobustElement[] = [];
    const peopleAlsoAsk: RobustElement[] = [];
    const videos: RobustElement[] = [];

    for (const el of snapshot.interactive_elements || []) {
      const tag = (el.tag || "").toLowerCase();
      const role = (el.role || "").toLowerCase();

      // Hygiene: anchors whose href is actually a CSS selector (lazy-load
      // skeleton templates, e.g. ".s-asin a:has(h2)") are not navigable —
      // clicking one produces junk URLs and 404 detours.
      if ((tag === "a" || role === "link") && this.looksLikeSelectorNotUrl(el.href || "")) {
        continue;
      }

      if (tag === "input" || tag === "textarea" || role === "textbox" || role === "searchbox") {
        inputs.push(el);
      } else if (tag === "select" || role === "combobox" || role === "listbox") {
        selects.push(el);
      } else if (tag === "button" || role === "button") {
        buttons.push(el);
      } else if (tag === "a" || role === "link" || el.href) {
        links.push(el);
      }
    }

    // Extract search results if on a search engine
    const searchResults: SearchResult[] = [];
    if (isSearchEngine) {
      this.extractGoogleSearchResults(snapshot, links, searchResults, advertisements, peopleAlsoAsk, videos);
    }

    return {
      url: snapshot.url,
      title: snapshot.title,
      sections: snapshot.headings || [],
      textBlocks: (snapshot as any).text_blocks || [],
      links,
      buttons,
      inputs,
      selects,
      searchResults,
      advertisements,
      peopleAlsoAsk,
      videos,
      formsCount: snapshot.forms_count || 0,
      tablesCount: snapshot.tables_count || 0,
      timestamp: snapshot.timestamp || new Date().toISOString(),
      observationFailed: snapshot.observation_failed ?? false,
      observationStatus: snapshot.observation_status || "OBSERVATION_SUCCESS",
    };
  }

  private static extractGoogleSearchResults(
    _snapshot: PerceptionSnapshot,
    links: RobustElement[],
    searchResults: SearchResult[],
    advertisements: RobustElement[],
    peopleAlsoAsk: RobustElement[],
    videos: RobustElement[]
  ) {
    let organicCounter = 1;

    for (const link of links) {
      const rawHref = link.href || "";
      const rawText = (link.text || link.name || "").trim();

      // Skip internal navigation & boilerplate Google links
      if (
        !rawHref ||
        rawHref.startsWith("javascript:") ||
        rawHref.startsWith("#") ||
        rawHref.includes("accounts.google.com") ||
        rawHref.includes("policies.google.com") ||
        rawHref.includes("support.google.com") ||
        rawHref.includes("maps.google.com") ||
        rawHref.includes("preferences") ||
        rawHref === "https://www.google.com/" ||
        rawHref === "https://google.com/"
      ) {
        continue;
      }

      // Detect domain
      let domain = "";
      try {
        const parsed = new URL(rawHref);
        domain = parsed.hostname.replace(/^www\./, "");
      } catch {
        domain = "";
      }

      // Classify Ads
      const isAd =
        rawText.toLowerCase().startsWith("sponsored") ||
        rawText.toLowerCase().includes(" ad ") ||
        rawHref.includes("googleadservices") ||
        rawHref.includes("aclk?");

      if (isAd) {
        advertisements.push(link);
        continue;
      }

      // Classify People Also Ask
      const isPAA =
        rawText.toLowerCase().includes("people also ask") ||
        (link.selector && link.selector.includes("related-question"));

      if (isPAA) {
        peopleAlsoAsk.push(link);
        continue;
      }

      if (domain === "google.com" || domain === "google.co.in") {
        continue;
      }

      // Classify Videos
      const isVideo =
        domain.includes("youtube.com") ||
        rawHref.includes("watch?v=") ||
        rawText.toLowerCase().includes("youtube");

      if (isVideo) {
        videos.push(link);
      }

      const isOrganic = !isAd && !isPAA;
      const rect = link.boundingBox || { x: 0, y: 0, width: 200, height: 40 };

      // Avoid duplicate results with identical URL
      if (!searchResults.some((r) => r.href === rawHref)) {
        searchResults.push({
          index: isOrganic ? organicCounter++ : 0,
          title: rawText || domain,
          href: rawHref,
          visibleText: rawText,
          domain,
          position: searchResults.length + 1,
          boundingRect: rect,
          isOrganic,
          isAdvertisement: !!isAd,
          isVideo,
          isShopping: domain.includes("amazon.") || domain.includes("flipkart.") || domain.includes("ebay."),
          isNews: domain.includes("news") || domain.includes("times") || domain.includes("ndtv") || domain.includes("reuters"),
          isPeopleAlsoAsk: !!isPAA,
          elementReference: link,
          confidence: 0.95,
        });
      }
    }
  }
}
