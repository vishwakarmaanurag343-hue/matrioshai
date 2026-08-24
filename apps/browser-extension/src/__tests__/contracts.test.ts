import { describe, it, expect } from 'vitest';
import { PlaceholderHeartbeatService } from '../background/service-worker';
import { MessageAction, BridgeAction } from '../shared/types';
import { browserBridge } from '../core/browser-bridge';

describe('MATRIOSHAI Future Phase Structural Contracts', () => {
  it('exposes defined MessageAction constants', () => {
    expect(MessageAction.PING).toBe('MATRIOSHAI_PING');
    expect(MessageAction.GET_STATUS).toBe('MATRIOSHAI_GET_STATUS');
    expect(MessageAction.CONTENT_SCRIPT_READY).toBe('MATRIOSHAI_CONTENT_SCRIPT_READY');
  });

  it('exposes Phase 2 BridgeAction constants', () => {
    expect(BridgeAction.AUTH).toBe('bridge.auth');
    expect(BridgeAction.HEALTH).toBe('bridge.health');
    expect(BridgeAction.INFO).toBe('bridge.info');
    expect(BridgeAction.PING).toBe('bridge.ping');
    expect(BridgeAction.STATUS).toBe('bridge.status');
  });

  it('real browser bridge implements IBrowserBridge contract', () => {
    expect(typeof browserBridge.connect).toBe('function');
    expect(typeof browserBridge.disconnect).toBe('function');
    expect(typeof browserBridge.getState).toBe('function');
    expect(typeof browserBridge.isAuthenticated).toBe('function');
    expect(typeof browserBridge.sendRequest).toBe('function');
    expect(typeof browserBridge.sendResponse).toBe('function');
  });

  it('placeholder heartbeat service conforms to contract', async () => {
    const heartbeat = new PlaceholderHeartbeatService();
    heartbeat.start(1000);
    const pingResult = await heartbeat.ping();
    expect(pingResult).toBe(true);
    heartbeat.stop();
  });
});
