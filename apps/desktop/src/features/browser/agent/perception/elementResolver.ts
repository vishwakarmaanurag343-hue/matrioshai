import { RobustElement } from "../types";
import { PageModel, ResolvedElement, SearchResult, SemanticTarget } from "./pageModel";

export class ElementResolver {
  /**
   * Generates a stable normalized search fingerprint for an element.
   */
  static generateFingerprint(el: Partial<RobustElement>, domain?: string): string {
    const parts = [
      el.role || el.tag || "elem",
      domain || "",
      (el.text || el.name || "").toLowerCase().trim().slice(0, 40),
      (el.href || "").split("?")[0].toLowerCase(),
      el.selector || "",
    ];
    return parts.filter(Boolean).join("::");
  }

  /**
   * Computes string similarity score between 0.0 and 1.0.
   */
  static stringSimilarity(a: string, b: string): number {
    const normalize = (s: string) =>
      (s || "")
        .toLowerCase()
        .replace(/[–—\-]/g, " ")
        .replace(/[^\w\s]/g, "")
        .trim();

    const s1 = normalize(a);
    const s2 = normalize(b);
    if (!s1 || !s2) return 0;
    if (s1 === s2) return 1.0;
    if (s1.includes(s2) || s2.includes(s1)) return 0.88;

    const words1 = new Set(s1.split(/\s+/).filter(Boolean));
    const words2 = new Set(s2.split(/\s+/).filter(Boolean));
    if (words1.size === 0 || words2.size === 0) return 0;

    const intersection = new Set([...words1].filter((x) => words2.has(x)));
    const union = new Set([...words1, ...words2]);
    const jaccard = intersection.size / union.size;
    const overlap = intersection.size / Math.min(words1.size, words2.size);

    return Math.max(jaccard, overlap * 0.85);
  }

  /**
   * Resolves search result by 1-indexed organic ordinal (e.g. 1st, 2nd, 3rd).
   */
  static resolveOrdinal(ordinal: number, searchResults: SearchResult[]): ResolvedElement | null {
    if (!searchResults || searchResults.length === 0 || ordinal <= 0) {
      return null;
    }

    const organicResults = searchResults.filter((r) => r.isOrganic && !r.isAdvertisement && !r.isPeopleAlsoAsk);
    const targetResult = organicResults[ordinal - 1];

    if (!targetResult) {
      return null;
    }

    return {
      element: targetResult.elementReference,
      strategy: "ordinal",
      confidence: 0.98,
      reason: `Resolved organic search result #${ordinal} ('${targetResult.title}')`,
      href: targetResult.href,
      text: targetResult.title,
      role: targetResult.elementReference.role || "link",
      boundingRect: targetResult.boundingRect,
      fingerprint: this.generateFingerprint(targetResult.elementReference, targetResult.domain),
    };
  }

  /**
   * Resolves element by destination domain (e.g. 'economictimes.indiatimes.com', 'amazon.in', 'kia.com').
   */
  static resolveByDomain(domainQuery: string, searchResults: SearchResult[], links: RobustElement[]): ResolvedElement | null {
    const cleanDomain = domainQuery.toLowerCase().replace(/^(https?:\/\/)?(www\.)?/, "").split("/")[0].trim();
    if (!cleanDomain) return null;

    // 1. Check Search Results
    for (const res of searchResults) {
      if (res.domain.toLowerCase().includes(cleanDomain) || cleanDomain.includes(res.domain.toLowerCase())) {
        return {
          element: res.elementReference,
          strategy: "domain",
          confidence: 0.95,
          reason: `Matched search result domain '${res.domain}' for '${cleanDomain}'`,
          href: res.href,
          text: res.title,
          role: res.elementReference.role || "link",
          boundingRect: res.boundingRect,
          fingerprint: this.generateFingerprint(res.elementReference, res.domain),
        };
      }
    }

    // 2. Check General Links
    for (const link of links) {
      if (link.href && link.href.toLowerCase().includes(cleanDomain)) {
        return {
          element: link,
          strategy: "domain",
          confidence: 0.88,
          reason: `Matched link href containing domain '${cleanDomain}'`,
          href: link.href,
          text: link.text || link.name || "",
          role: link.role || "link",
          boundingRect: link.boundingBox || { x: 0, y: 0, width: 0, height: 0 },
          fingerprint: this.generateFingerprint(link, cleanDomain),
        };
      }
    }

    return null;
  }

  /**
   * Resolves element by text similarity.
   */
  static resolveByText(textQuery: string, elements: RobustElement[]): ResolvedElement | null {
    if (!textQuery || !elements || elements.length === 0) return null;

    let bestElem: RobustElement | null = null;
    let highestScore = 0;

    for (const el of elements) {
      const candidateText = `${el.text || ""} ${el.name || ""} ${el.ariaLabel || ""}`.trim();
      const score = this.stringSimilarity(textQuery, candidateText);

      if (score > highestScore && score >= 0.65) {
        highestScore = score;
        bestElem = el;
      }
    }

    if (!bestElem) return null;

    return {
      element: bestElem,
      strategy: "text",
      confidence: highestScore,
      reason: `Matched text similarity (${Math.round(highestScore * 100)}%) for '${textQuery}'`,
      href: bestElem.href || "",
      text: bestElem.text || bestElem.name || "",
      role: bestElem.role || bestElem.tag || "element",
      boundingRect: bestElem.boundingBox || { x: 0, y: 0, width: 0, height: 0 },
      fingerprint: this.generateFingerprint(bestElem),
    };
  }

  /**
   * Central Semantic Element Dispatcher.
   * Resolves any semantic intent into a live DOM element from the current observation.
   */
  static resolveBestCandidate(target: SemanticTarget | string, pageModel: PageModel): ResolvedElement | null {
    if (!target) return null;

    // Handle plain string (e.g. element_id or text)
    if (typeof target === "string") {
      // 1. Direct ID match from current observation
      const direct = pageModel.links
        .concat(pageModel.buttons)
        .concat(pageModel.inputs)
        .find((e) => e.id === target);

      if (direct) {
        return {
          element: direct,
          strategy: "direct_id",
          confidence: 1.0,
          reason: `Matched active observation element ID '${target}'`,
          href: direct.href || "",
          text: direct.text || direct.name || "",
          role: direct.role || direct.tag || "element",
          boundingRect: direct.boundingBox || { x: 0, y: 0, width: 0, height: 0 },
          fingerprint: this.generateFingerprint(direct),
        };
      }

      // Check if string contains ordinal or priority intent (e.g. "3rd website", "first result", "best result", "the ebist", "frist websit")
      const lower = target.toLowerCase();
      if (
        lower.includes("1st") ||
        lower.includes("first") ||
        lower.includes("frist") ||
        lower.includes("frst") ||
        lower.includes("fst") ||
        lower.includes("best") ||
        lower.includes("ebist") ||
        lower.includes("top result") ||
        lower.includes("top website") ||
        lower.includes("official")
      ) {
        return this.resolveOrdinal(1, pageModel.searchResults);
      }
      if (lower.includes("2nd") || lower.includes("second") || lower.includes("scnd") || lower.includes("secnd")) return this.resolveOrdinal(2, pageModel.searchResults);
      if (lower.includes("3rd") || lower.includes("third") || lower.includes("thrd") || lower.includes("trd")) return this.resolveOrdinal(3, pageModel.searchResults);
      if (lower.includes("4th") || lower.includes("fourth") || lower.includes("forth") || lower.includes("frth")) return this.resolveOrdinal(4, pageModel.searchResults);
      if (lower.includes("5th") || lower.includes("fifth") || lower.includes("fith")) return this.resolveOrdinal(5, pageModel.searchResults);

      // Fallback text match
      return this.resolveByText(target, pageModel.links.concat(pageModel.buttons).concat(pageModel.inputs));
    }

    // 1. Ordinal Resolution
    if (target.ordinal && target.ordinal > 0) {
      const ord = this.resolveOrdinal(target.ordinal, pageModel.searchResults);
      if (ord) return ord;
    }

    // 2. Domain Resolution
    if (target.domain) {
      const dom = this.resolveByDomain(target.domain, pageModel.searchResults, pageModel.links);
      if (dom) return dom;
    }

    // 3. Text / Description Resolution
    if (target.text || target.description) {
      const query = target.text || target.description || "";

      // Check searchResults first
      for (const res of pageModel.searchResults) {
        const score = this.stringSimilarity(query, `${res.title} ${res.visibleText} ${res.domain}`);
        if (score >= 0.50) {
          return {
            element: res.elementReference,
            strategy: "text",
            confidence: score,
            reason: `Matched search result text '${res.title}' for query '${query}'`,
            href: res.href,
            text: res.title,
            role: res.elementReference.role || "link",
            boundingRect: res.boundingRect,
            fingerprint: this.generateFingerprint(res.elementReference, res.domain),
          };
        }
      }

      const txt = this.resolveByText(query, pageModel.links.concat(pageModel.buttons).concat(pageModel.inputs));
      if (txt) return txt;
    }

    return null;
  }

  /**
   * Compatibility wrapper for existing tests.
   */
  static resolveElement(
    targetHint: string | Partial<RobustElement>,
    activeElements: RobustElement[]
  ): { element: RobustElement | null; confidence: number; recovered: boolean } {
    if (!activeElements || activeElements.length === 0) {
      return { element: null, confidence: 0, recovered: false };
    }

    if (typeof targetHint === "string") {
      const exactMatch = activeElements.find((e) => e.id === targetHint);
      if (exactMatch) {
        return { element: exactMatch, confidence: 1.0, recovered: false };
      }
    }

    const textQuery = typeof targetHint === "string" ? targetHint : targetHint.text || targetHint.name || "";
    const resolved = this.resolveByText(textQuery, activeElements);

    return {
      element: resolved ? resolved.element : null,
      confidence: resolved ? resolved.confidence : 0,
      recovered: !!resolved,
    };
  }

  /**
   * Classifies form fields for intelligent form handling and sensitive data masking.
   */
  static classifyFormField(element: RobustElement): {
    fieldType: "search" | "email" | "password" | "phone" | "text" | "submit" | "select" | "checkbox";
    isRequired: boolean;
    isSensitive: boolean;
  } {
    const raw = `${element.name || ""} ${element.selector || ""} ${element.role || ""} ${element.tag || ""}`.toLowerCase();
    const isPass = raw.includes("pass") || !!element.sensitive;
    const isEmail = raw.includes("email") || raw.includes("mail");
    const isSearch = raw.includes("search") || raw.includes("query") || element.role === "searchbox";

    let fieldType: "search" | "email" | "password" | "phone" | "text" | "submit" | "select" | "checkbox" = "text";
    if (isPass) fieldType = "password";
    else if (isEmail) fieldType = "email";
    else if (isSearch) fieldType = "search";
    else if (element.role === "button" || element.tag === "button") fieldType = "submit";

    return {
      fieldType,
      isRequired: raw.includes("required") || raw.includes("*"),
      isSensitive: isPass || isEmail,
    };
  }
}
