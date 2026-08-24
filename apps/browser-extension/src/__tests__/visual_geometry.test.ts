// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest';
import { VisualGeometry } from '../content/visual-geometry';

describe('MATRIOSHAI Visual Geometry & Coordinate Transformations (Phase 6)', () => {
  it('converts DOM coordinates to Screenshot coordinates across varying DPRs', () => {
    const domBox = VisualGeometry.createBox(100, 200, 300, 50, 'DOM_VIEWPORT');

    // DPR = 1.0
    const screenBox1 = VisualGeometry.domToScreenshotCoordinates(domBox, 1.0, 1.0);
    expect(screenBox1.x).toBe(100);
    expect(screenBox1.y).toBe(200);
    expect(screenBox1.width).toBe(300);
    expect(screenBox1.height).toBe(50);
    expect(screenBox1.coordinate_system).toBe('SCREENSHOT_PIXEL');

    // DPR = 2.0 (Retina)
    const screenBox2 = VisualGeometry.domToScreenshotCoordinates(domBox, 2.0, 1.0);
    expect(screenBox2.x).toBe(200);
    expect(screenBox2.y).toBe(400);
    expect(screenBox2.width).toBe(600);
    expect(screenBox2.height).toBe(100);

    // DPR = 1.5 with scaling factor 0.8
    const screenBoxScale = VisualGeometry.domToScreenshotCoordinates(domBox, 1.5, 0.8);
    // effectiveFactor = 1.5 * 0.8 = 1.2
    expect(screenBoxScale.x).toBe(120);
    expect(screenBoxScale.y).toBe(240);
    expect(screenBoxScale.width).toBe(360);
    expect(screenBoxScale.height).toBe(60);
  });

  it('accurately roundtrips screenshot to DOM coordinates', () => {
    const originalDom = VisualGeometry.createBox(50, 80, 200, 40, 'DOM_VIEWPORT');
    const screenBox = VisualGeometry.domToScreenshotCoordinates(originalDom, 2.0, 1.0);
    const convertedBack = VisualGeometry.screenshotToDomCoordinates(screenBox, 2.0, 1.0);

    expect(convertedBack.x).toBe(originalDom.x);
    expect(convertedBack.y).toBe(originalDom.y);
    expect(convertedBack.width).toBe(originalDom.width);
    expect(convertedBack.height).toBe(originalDom.height);
    expect(convertedBack.coordinate_system).toBe('DOM_VIEWPORT');
  });

  it('converts between document space and viewport space with scroll offsets', () => {
    const docBox = VisualGeometry.createBox(150, 800, 200, 100, 'DOCUMENT_SPACE');
    const scrollX = 0;
    const scrollY = 500;

    const viewBox = VisualGeometry.documentToViewportCoordinates(docBox, scrollX, scrollY);
    expect(viewBox.x).toBe(150);
    expect(viewBox.y).toBe(300); // 800 - 500
    expect(viewBox.coordinate_system).toBe('DOM_VIEWPORT');

    const backToDoc = VisualGeometry.viewportToDocumentCoordinates(viewBox, scrollX, scrollY);
    expect(backToDoc.y).toBe(800);
    expect(backToDoc.coordinate_system).toBe('DOCUMENT_SPACE');
  });

  it('evaluates geometric point containment, rectangle intersection, and containment', () => {
    const boxA = VisualGeometry.createBox(10, 10, 100, 100);
    const boxB = VisualGeometry.createBox(50, 50, 40, 40); // Inside boxA
    const boxC = VisualGeometry.createBox(80, 80, 100, 100); // Overlaps boxA
    const boxD = VisualGeometry.createBox(300, 300, 50, 50); // Disjoint

    expect(VisualGeometry.containsPoint(boxA, 50, 50)).toBe(true);
    expect(VisualGeometry.containsPoint(boxA, 5, 5)).toBe(false);

    expect(VisualGeometry.containsRect(boxA, boxB)).toBe(true);
    expect(VisualGeometry.containsRect(boxA, boxC)).toBe(false);

    expect(VisualGeometry.intersectsRect(boxA, boxC)).toBe(true);
    expect(VisualGeometry.intersectsRect(boxA, boxD)).toBe(false);

    expect(VisualGeometry.distanceToPoint(boxA, 50, 50)).toBe(0);
    expect(VisualGeometry.distanceToPoint(boxA, 115, 10)).toBe(5); // dx = 115 - 110 = 5
  });

  it('classifies element visibility states against viewport boundaries', () => {
    const viewportWidth = 1000;
    const viewportHeight = 800;

    // Fully inside
    const fullBox = VisualGeometry.createBox(100, 100, 200, 100);
    expect(VisualGeometry.classifyVisibility(fullBox, viewportWidth, viewportHeight)).toBe('fully_visible');

    // Partially inside top edge
    const partialTop = VisualGeometry.createBox(100, -30, 200, 100);
    expect(VisualGeometry.classifyVisibility(partialTop, viewportWidth, viewportHeight)).toBe('partially_visible');

    // Partially inside right edge
    const partialRight = VisualGeometry.createBox(900, 100, 200, 100);
    expect(VisualGeometry.classifyVisibility(partialRight, viewportWidth, viewportHeight)).toBe('partially_visible');

    // Completely outside
    const outsideBox = VisualGeometry.createBox(100, 900, 200, 100);
    expect(VisualGeometry.classifyVisibility(outsideBox, viewportWidth, viewportHeight)).toBe('outside_viewport');

    // Zero size
    const zeroBox = VisualGeometry.createBox(100, 100, 0, 0);
    expect(VisualGeometry.classifyVisibility(zeroBox, viewportWidth, viewportHeight)).toBe('hidden');
  });
});
