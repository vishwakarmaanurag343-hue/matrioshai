import { describe, it, expect, beforeEach } from "vitest";
import { ElementResolver } from "../perception/elementResolver";
import { PageModel, RobustElement } from "../types";

describe("Phase 8D — Advanced Target Resolution V3 Engine Suite", () => {
  let mockPageModel: PageModel;

  beforeEach(() => {
    mockPageModel = {
      url: "https://shop.example.com/checkout",
      title: "Checkout",
      sections: [],
      links: [
        {
          id: "link_nested_1",
          name: "Item 1 Detail",
          role: "link",
          tag: "a",
          text: "Item 1 Detail",
          href: "https://shop.example.com/item/1",
          selector: "a.item-link",
          sensitive: false,
          boundingBox: { x: 10, y: 10, width: 100, height: 20 },
          visible: true,
          enabled: true,
        },
      ],
      buttons: [
        {
          id: "btn_buy_1",
          name: "Buy Now",
          role: "button",
          tag: "button",
          text: "Buy Now",
          href: "",
          selector: "button.buy-top",
          sensitive: false,
          boundingBox: { x: 10, y: 50, width: 120, height: 35 },
          visible: true,
          enabled: true,
        },
        {
          id: "btn_buy_2",
          name: "Buy Now",
          role: "button",
          tag: "button",
          text: "Buy Now",
          href: "",
          selector: "button.buy-bottom",
          sensitive: false,
          boundingBox: { x: 10, y: 300, width: 120, height: 35 },
          visible: true,
          enabled: true,
        },
        {
          id: "btn_hidden",
          name: "Submit Order",
          role: "button",
          tag: "button",
          text: "Submit Order",
          href: "",
          selector: "button.hidden",
          sensitive: false,
          boundingBox: { x: 0, y: 0, width: 0, height: 0 },
          visible: false,
          enabled: true,
        },
        {
          id: "btn_disabled",
          name: "Checkout Disabled",
          role: "button",
          tag: "button",
          text: "Checkout Disabled",
          href: "",
          selector: "button.disabled",
          sensitive: false,
          boundingBox: { x: 10, y: 400, width: 120, height: 35 },
          visible: true,
          enabled: false,
          disabled: true,
        },
        {
          id: "btn_obscured",
          name: "Obscured Target",
          role: "button",
          tag: "button",
          text: "Obscured Target",
          href: "",
          selector: "button.obscured",
          sensitive: false,
          boundingBox: { x: 10, y: 500, width: 120, height: 35 },
          visible: true,
          enabled: true,
          obscured: true,
        } as RobustElement & { obscured?: boolean },
      ],
      inputs: [],
      selects: [],
      searchResults: [
        {
          title: "Organic Result #1",
          url: "https://example.com/res1",
          domain: "example.com",
          href: "https://example.com/res1",
          snippet: "Snippet 1",
          isOrganic: true,
          isAdvertisement: false,
          isPeopleAlsoAsk: false,
          boundingRect: { x: 10, y: 100, width: 200, height: 30 },
          elementReference: {
            id: "el_res_1",
            role: "link",
            tag: "a",
            text: "Organic Result #1",
            selector: "a.res1",
          },
        },
        {
          title: "Organic Result #2",
          url: "https://example.com/res2",
          domain: "example.com",
          href: "https://example.com/res2",
          snippet: "Snippet 2",
          isOrganic: true,
          isAdvertisement: false,
          isPeopleAlsoAsk: false,
          boundingRect: { x: 10, y: 150, width: 200, height: 30 },
          elementReference: {
            id: "el_res_2",
            role: "link",
            tag: "a",
            text: "Organic Result #2",
            selector: "a.res2",
          },
        },
      ],
      advertisements: [],
      peopleAlsoAsk: [],
      videos: [],
      formsCount: 1,
      tablesCount: 0,
      timestamp: new Date().toISOString(),
    };
  });

  it("1. duplicate text candidates: fails closed on margin ambiguity (<0.98 score)", () => {
    // Two identical "Buy Now" buttons share score ~0.88 without exact query string match -> returns null
    const res = ElementResolver.resolveBestCandidate("Buy", mockPageModel);
    expect(res).toBeNull();
  });

  it("2. direct exact match: resolves unambiguously", () => {
    const res = ElementResolver.resolveBestCandidate("Item 1 Detail", mockPageModel);
    expect(res).not.toBeNull();
    expect(res?.confidence).toBeGreaterThanOrEqual(0.88);
  });

  it("3. ordinal resolution: resolves 1st and 2nd organic search results", () => {
    const res1 = ElementResolver.resolveBestCandidate("first result", mockPageModel);
    expect(res1?.element.id).toBe("el_res_1");

    const res2 = ElementResolver.resolveBestCandidate("2nd result", mockPageModel);
    expect(res2?.element.id).toBe("el_res_2");
  });

  it("4. hidden candidate rejection: fails closed when target element is invisible", () => {
    const res = ElementResolver.resolveBestCandidate("Submit Order", mockPageModel);
    expect(res).toBeNull();
  });

  it("5. disabled candidate rejection: fails closed when target element is disabled", () => {
    const res = ElementResolver.resolveBestCandidate("Checkout Disabled", mockPageModel);
    expect(res).toBeNull();
  });

  it("6. obscured candidate rejection: penalizes score and fails closed", () => {
    const res = ElementResolver.resolveBestCandidate("Obscured Target", mockPageModel);
    expect(res).toBeNull();
  });
});
