import { describe, it, expect, beforeEach } from 'vitest';
import { ExtensionStateManager } from '../core/extension-state';

describe('MATRIOSHAI Extension State Manager', () => {
  let stateManager: ExtensionStateManager;

  beforeEach(() => {
    stateManager = new ExtensionStateManager();
  });

  it('initializes with expected default values', () => {
    const state = stateManager.getState();
    expect(state.installed).toBe(false);
    expect(state.serviceWorkerReady).toBe(false);
    expect(state.contentScriptReady).toBe(false);
    expect(state.lastError).toBeNull();
    expect(state.extensionVersion).toBe('0.1.0');
  });

  it('updates state fields and triggers listeners', async () => {
    let notified = false;
    stateManager.subscribe((state) => {
      if (state.serviceWorkerReady) {
        notified = true;
      }
    });

    await stateManager.setServiceWorkerReady(true);
    const updated = stateManager.getState();
    expect(updated.serviceWorkerReady).toBe(true);
    expect(notified).toBe(true);
  });

  it('records and clears errors correctly', async () => {
    await stateManager.recordError('Simulated runtime error');
    expect(stateManager.getState().lastError).toBe('Simulated runtime error');

    await stateManager.clearError();
    expect(stateManager.getState().lastError).toBeNull();
  });

  it('supports unsubscription from state listeners', async () => {
    let callCount = 0;
    const unsubscribe = stateManager.subscribe(() => {
      callCount++;
    });

    await stateManager.updateState({ installed: true });
    expect(callCount).toBe(1);

    unsubscribe();
    await stateManager.updateState({ initialized: true });
    expect(callCount).toBe(1);
  });
});
