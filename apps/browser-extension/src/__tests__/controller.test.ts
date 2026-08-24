import { describe, it, expect } from 'vitest';
import { BrowserController } from '../core/browser-controller';
import { PHASE_3_CAPABILITIES } from '../shared/constants';

describe('MATRIOSHAI Browser Controller (Phase 3)', () => {
  const controller = new BrowserController();

  it('validates normal web URLs', () => {
    const res1 = controller.validateUrl('https://example.com/test');
    expect(res1.valid).toBe(true);
    expect(res1.normalizedUrl).toBe('https://example.com/test');

    const res2 = controller.validateUrl('http://localhost:8765/page');
    expect(res2.valid).toBe(true);
    expect(res2.normalizedUrl).toBe('http://localhost:8765/page');

    const res3 = controller.validateUrl('example.com');
    expect(res3.valid).toBe(true);
    expect(res3.normalizedUrl).toBe('https://example.com');
  });

  it('strictly rejects dangerous URL schemes', () => {
    const res1 = controller.validateUrl('javascript:alert(1)');
    expect(res1.valid).toBe(false);
    expect(res1.error).toContain('Dangerous or unsupported URL scheme');

    const res2 = controller.validateUrl('data:text/html,<h1>Hacked</h1>');
    expect(res2.valid).toBe(false);
    expect(res2.error).toContain('Dangerous or unsupported URL scheme');

    const res3 = controller.validateUrl('file:///etc/passwd');
    expect(res3.valid).toBe(false);
    expect(res3.error).toContain('Dangerous or unsupported URL scheme');

    const res4 = controller.validateUrl('vbscript:msgbox("test")');
    expect(res4.valid).toBe(false);
  });

  it('rejects empty or invalid URLs', () => {
    const res1 = controller.validateUrl('');
    expect(res1.valid).toBe(false);

    const res2 = controller.validateUrl('   ');
    expect(res2.valid).toBe(false);
  });

  it('registers all Phase 3 capabilities', () => {
    expect(PHASE_3_CAPABILITIES).toContain('browser.getStatus');
    expect(PHASE_3_CAPABILITIES).toContain('browser.getWindows');
    expect(PHASE_3_CAPABILITIES).toContain('browser.getTabs');
    expect(PHASE_3_CAPABILITIES).toContain('browser.getActiveTab');
    expect(PHASE_3_CAPABILITIES).toContain('browser.openTab');
    expect(PHASE_3_CAPABILITIES).toContain('browser.switchTab');
    expect(PHASE_3_CAPABILITIES).toContain('browser.closeTab');
    expect(PHASE_3_CAPABILITIES).toContain('browser.navigate');
    expect(PHASE_3_CAPABILITIES).toContain('browser.reload');
    expect(PHASE_3_CAPABILITIES).toContain('browser.goBack');
    expect(PHASE_3_CAPABILITIES).toContain('browser.goForward');
    expect(PHASE_3_CAPABILITIES).toContain('browser.waitForNavigation');
    expect(PHASE_3_CAPABILITIES).toContain('browser.refreshState');
  });
});
