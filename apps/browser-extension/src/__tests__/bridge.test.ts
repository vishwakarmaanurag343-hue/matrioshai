import { describe, it, expect, beforeEach } from 'vitest';
import { BrowserBridgeClient } from '../core/browser-bridge';
import { PHASE_14_CAPABILITIES } from '../shared/constants';
import { BridgeAction } from '../shared/types';

describe('MATRIOSHAI Browser Bridge Client (Phases 2-14)', () => {
  let bridge: BrowserBridgeClient;

  beforeEach(() => {
    bridge = new BrowserBridgeClient('ws://127.0.0.1:8000/api/v1/browser/bridge/ws');
  });

  it('initializes in DISCONNECTED state', () => {
    expect(bridge.getState()).toBe('DISCONNECTED');
    expect(bridge.isAuthenticated()).toBe(false);
    expect(bridge.getSessionId()).toBeNull();
  });

  it('advertises strictly Phases 2-14 capabilities', () => {
    const caps = bridge.getAdvertisedCapabilities();
    expect(caps).toEqual([...PHASE_14_CAPABILITIES]);
    expect(caps).toContain(BridgeAction.AUTH);
    expect(caps).toContain(BridgeAction.HEALTH);
    expect(caps).toContain(BridgeAction.INFO);
    expect(caps).toContain(BridgeAction.PING);
    expect(caps).toContain(BridgeAction.STATUS);
    expect(caps).toContain(BridgeAction.BROWSER_GET_TABS);
    expect(caps).toContain(BridgeAction.BROWSER_NAVIGATE);
    expect(caps).toContain(BridgeAction.PAGE_OBSERVE);
    expect(caps).toContain(BridgeAction.PAGE_SEMANTIC_OBSERVE);
    expect(caps).toContain(BridgeAction.PAGE_SEMANTIC_QUERY);
    expect(caps).toContain(BridgeAction.PAGE_RESOLVE_ELEMENT);
    expect(caps).toContain(BridgeAction.PAGE_CAPTURE_SCREENSHOT);
    expect(caps).toContain(BridgeAction.PAGE_VISUAL_OBSERVE);
    expect(caps).toContain(BridgeAction.PAGE_GET_VISUAL_MODEL);
    expect(caps).toContain(BridgeAction.PAGE_VISUAL_POINT_QUERY);
    expect(caps).toContain(BridgeAction.PAGE_VISUAL_QUERY);
    expect(caps).toContain(BridgeAction.WORLD_GET_CURRENT);
    expect(caps).toContain(BridgeAction.WORLD_GET_SNAPSHOT);
    expect(caps).toContain(BridgeAction.WORLD_GET_DIFF);
    expect(caps).toContain(BridgeAction.WORLD_QUERY);
    expect(caps).toContain(BridgeAction.WORLD_RESOLVE_ELEMENT);
    expect(caps).toContain(BridgeAction.ACTION_EXECUTE);
    expect(caps).toContain(BridgeAction.ACTION_CANCEL);
    expect(caps).toContain(BridgeAction.ACTION_CONFIRM);
    expect(caps).toContain(BridgeAction.VERIFICATION_VERIFY);
    expect(caps).toContain(BridgeAction.RECOVERY_RECOMMEND);
    expect(caps).toContain(BridgeAction.CHECKPOINT_CREATE);
    expect(caps).toContain(BridgeAction.AGENT_CREATE_GOAL);
    expect(caps).toContain(BridgeAction.AGENT_START_TASK);
    expect(caps).toContain(BridgeAction.AGENT_PAUSE_TASK);
    expect(caps).toContain(BridgeAction.AGENT_RESUME_TASK);
    expect(caps).toContain(BridgeAction.AGENT_ABORT_TASK);
    expect(caps).toContain(BridgeAction.AGENT_GET_TASK);
    expect(caps).toContain(BridgeAction.TRANSACTION_CREATE);
    expect(caps).toContain(BridgeAction.TRANSACTION_SELECT_OPTION);
    expect(caps).toContain(BridgeAction.TRANSACTION_PREPARE_REVIEW);
    expect(caps).toContain(BridgeAction.TRANSACTION_CONFIRM);
    expect(caps).toContain(BridgeAction.TRANSACTION_COMMIT);
    expect(caps).toContain(BridgeAction.TRANSACTION_CANCEL);
    expect(caps).toContain(BridgeAction.TRANSACTION_GET);
    expect(caps).toContain(BridgeAction.TRANSACTION_GET_RECEIPT);
    expect(caps).toContain(BridgeAction.SECURITY_EVALUATE);
    expect(caps).toContain(BridgeAction.SECURITY_GRANT_PERMISSION);
    expect(caps).toContain(BridgeAction.SECURITY_REVOKE_PERMISSION);
    expect(caps).toContain(BridgeAction.SECURITY_EMERGENCY_STOP);
    expect(caps).toContain(BridgeAction.SECURITY_SET_TAKEOVER);
    expect(caps).toContain(BridgeAction.SECURITY_GET_STATE);
    expect(caps).toContain(BridgeAction.SECURITY_GET_AUDIT_LOGS);
    expect(caps).toContain(BridgeAction.RUNTIME_HEALTH);
    expect(caps).toContain(BridgeAction.RUNTIME_STATUS);
    expect(caps).toContain(BridgeAction.RUNTIME_SUPERVISOR);
    expect(caps).toContain(BridgeAction.RUNTIME_METRICS);
    expect(caps).toContain(BridgeAction.RUNTIME_EVENTS);
    expect(caps).toContain(BridgeAction.RUNTIME_DEAD_LETTER_QUEUE);
    expect(caps).toContain(BridgeAction.CHAOS_INJECT_FAULT);

    // Strictly ensure no arbitrary code execution or upload/download capabilities
    expect(caps).not.toContain('browser.executeScript');
    expect(caps).not.toContain('browser.fileUpload');
  });

  it('notifies subscribers on state transitions', () => {
    const states: string[] = [];
    bridge.subscribe((state) => {
      states.push(state);
    });

    // Simulate internal state updates
    (bridge as unknown as { setState: (s: string) => void }).setState('CONNECTING');
    (bridge as unknown as { setState: (s: string) => void }).setState('CONNECTED');
    (bridge as unknown as { setState: (s: string) => void }).setState('READY');

    expect(states).toEqual(['CONNECTING', 'CONNECTED', 'READY']);
    expect(bridge.isAuthenticated()).toBe(true);
  });

  it('rejects sendRequest when bridge is not in READY state', async () => {
    await expect(bridge.sendRequest('bridge.ping', {})).rejects.toThrow('Bridge is not ready');
  });

  it('cleans up pending requests on disconnect', async () => {
    await bridge.disconnect();
    expect(bridge.getState()).toBe('DISCONNECTED');
  });
});
