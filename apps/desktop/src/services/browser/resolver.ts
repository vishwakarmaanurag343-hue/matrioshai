export interface SearchEngine {
  id: string;
  name: string;
  searchUrlTemplate: string;
  suggestionUrlTemplate?: string;
  enabled: boolean;
}

export const SEARCH_ENGINES: Record<string, SearchEngine> = {
  google: {
    id: "google",
    name: "Google",
    searchUrlTemplate: "https://www.google.com/search?q={query}",
    enabled: true,
  },
  duckduckgo: {
    id: "duckduckgo",
    name: "DuckDuckGo",
    searchUrlTemplate: "https://duckduckgo.com/?q={query}",
    enabled: true,
  },
  brave: {
    id: "brave",
    name: "Brave Search",
    searchUrlTemplate: "https://search.brave.com/search?q={query}",
    suggestionUrlTemplate: "https://search.brave.com/api/suggest?q={query}",
    enabled: true,
  },
  bing: {
    id: "bing",
    name: "Bing",
    searchUrlTemplate: "https://www.bing.com/search?q={query}",
    suggestionUrlTemplate: "https://api.bing.com/osjson.aspx?query={query}",
    enabled: true,
  },
  startpage: {
    id: "startpage",
    name: "Startpage",
    searchUrlTemplate: "https://www.startpage.com/sp/search?query={query}",
    enabled: true,
  },
  ecosia: {
    id: "ecosia",
    name: "Ecosia",
    searchUrlTemplate: "https://www.ecosia.org/search?q={query}",
    suggestionUrlTemplate: "https://ac.ecosia.org/autocomplete?q={query}&type=list",
    enabled: true,
  },
};

export type InputCategory =
  | "DIRECT_URL"
  | "SEARCH_QUERY"
  | "LOCAL_ADDRESS"
  | "UNSUPPORTED_PROTOCOL";

export class SearchEngineResolver {
  /**
   * Classifies user input into URL categories.
   */
  static classify(input: string): InputCategory {
    const trimmed = input.trim();
    if (!trimmed) return "SEARCH_QUERY";

    if (
      trimmed.startsWith("http://") ||
      trimmed.startsWith("https://") ||
      trimmed.startsWith("about:")
    ) {
      return "DIRECT_URL";
    }

    if (
      trimmed.startsWith("mailto:") ||
      trimmed.startsWith("tel:") ||
      trimmed.startsWith("javascript:") ||
      trimmed.startsWith("data:")
    ) {
      return "UNSUPPORTED_PROTOCOL";
    }

    if (
      trimmed.startsWith("localhost") ||
      trimmed.startsWith("127.0.0.1") ||
      /^(\d{1,3}\.){3}\d{1,3}(:\d+)?$/.test(trimmed)
    ) {
      return "LOCAL_ADDRESS";
    }

    // Check if input looks like a domain name (e.g. google.com, sub.example.org/path)
    const isDomain =
      !trimmed.includes(" ") &&
      trimmed.includes(".") &&
      !trimmed.endsWith(".") &&
      /^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(\/.*)?$/.test(trimmed);

    if (isDomain) {
      return "DIRECT_URL";
    }

    return "SEARCH_QUERY";
  }

  /**
   * Resolves address bar user input:
   * 1. Valid URLs / Schemes -> returned as-is
   * 2. Local addresses / Domains -> normalized to http(s)://...
   * 3. Plain search queries -> resolved to destination search engine URL directly.
   */
  static resolve(input: string, engineId: string = "google"): string {
    const trimmed = input.trim();
    if (!trimmed) return "about:blank";

    const category = this.classify(trimmed);

    if (category === "DIRECT_URL") {
      if (
        trimmed.startsWith("http://") ||
        trimmed.startsWith("https://") ||
        trimmed.startsWith("about:")
      ) {
        return trimmed;
      }
      return `https://${trimmed}`;
    }

    if (category === "LOCAL_ADDRESS") {
      if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
        return trimmed;
      }
      return `http://${trimmed}`;
    }

    if (category === "UNSUPPORTED_PROTOCOL") {
      return trimmed;
    }

    // Construct search query URL
    const engine = SEARCH_ENGINES[engineId] || SEARCH_ENGINES.google;
    return engine.searchUrlTemplate.replace("{query}", encodeURIComponent(trimmed));
  }

  /**
   * Fetches search query suggestions from DuckDuckGo/Google autocompletion APIs.
   */
  static async fetchSuggestions(query: string): Promise<string[]> {
    const trimmed = query.trim();
    if (!trimmed || trimmed.length < 2) return [];

    try {
      const response = await fetch(
        `https://duckduckgo.com/ac/?q=${encodeURIComponent(trimmed)}&type=list`
      );
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data) && Array.isArray(data[1])) {
          return data[1].slice(0, 6);
        }
      }
    } catch {
      // Fallback silent
    }
    return [];
  }
}
