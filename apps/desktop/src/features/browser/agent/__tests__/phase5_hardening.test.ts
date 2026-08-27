import { describe, it, expect, beforeEach } from "vitest";
import { ElementResolver } from "../perception/elementResolver";
import { PageModel } from "../types";

describe("Phase 5A — Real-World Hardening & Popover Dropdown Resolution Suite", () => {
  let mockPageModel: PageModel;

  beforeEach(() => {
    mockPageModel = {
      url: "https://app.example.com/settings",
      title: "Settings",
      sections: [],
      links: [],
      buttons: [
        {
          id: "el_popover_1",
          name: "Select Region Dropdown",
          role: "combobox",
          tag: "button",
          text: "Select Region Dropdown",
          href: "",
          selector: "button[role='combobox']",
          sensitive: false,
          boundingBox: { x: 10, y: 50, width: 150, height: 35 },
          visible: true,
          enabled: true,
        },
      ],
      inputs: [],
      selects: [],
      searchResults: [],
      advertisements: [],
      peopleAlsoAsk: [],
      videos: [],
      formsCount: 1,
      tablesCount: 0,
      timestamp: new Date().toISOString(),
    };
  });

  it("popover resolution: matches dynamic ARIA combobox trigger element", () => {
    const res = ElementResolver.resolveBestCandidate("Select Region Dropdown", mockPageModel);

    expect(res).not.toBeNull();
    expect(res?.element.id).toBe("el_popover_1");
    expect(res?.role).toBe("combobox");
    expect(res?.confidence).toBeGreaterThanOrEqual(0.90);
  });
});
