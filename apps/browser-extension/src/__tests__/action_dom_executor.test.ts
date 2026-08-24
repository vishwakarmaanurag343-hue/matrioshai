// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ActionDomExecutor } from '../content/action-dom-executor';
import { type ActionIntent } from '../shared/types';

describe('MATRIOSHAI Safe DOM Action Executor (Phase 8)', () => {
  let executor: ActionDomExecutor;

  beforeEach(() => {
    executor = new ActionDomExecutor();
    document.body.innerHTML = `
      <div id="container">
        <button id="btn-submit" data-matrioshai-id="elem_btn_1">Submit Order</button>
        <button id="btn-disabled" disabled>Unavailable</button>
        
        <input type="text" id="username-input" data-matrioshai-id="elem_input_1" value="Alice" />
        <input type="checkbox" id="terms-check" data-matrioshai-id="elem_check_1" />
        <input type="checkbox" id="newsletter-check" checked />

        <select id="country-select" data-matrioshai-id="elem_select_1">
          <option value="US">United States</option>
          <option value="CA">Canada</option>
          <option value="UK">United Kingdom</option>
        </select>

        <div id="editor" contenteditable="true">Initial text</div>
      </div>
    `;
  });

  it('executes CLICK on active button dispatching full event sequence', () => {
    const btn = document.getElementById('btn-submit')!;
    const clickSpy = vi.fn();
    btn.addEventListener('click', clickSpy);

    const intent: ActionIntent = {
      action_id: 'act_click_1',
      type: 'CLICK',
      target: {
        world_element_ref: {
          page_id: 'page_1',
          observation_id: 'obs_1',
          element_id: 'elem_btn_1',
          page_version: 1
        }
      },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    };

    const res = executor.executeAction(intent);
    expect(res.status).toBe('SUCCESS');
    expect(clickSpy).toHaveBeenCalled();
  });

  it('rejects CLICK on disabled button with TARGET_DISABLED', () => {
    const intent: ActionIntent = {
      action_id: 'act_click_disabled',
      type: 'CLICK',
      target: {
        world_element_ref: {
          page_id: 'page_1',
          observation_id: 'obs_1',
          element_id: 'elem_disabled',
          stable_dom_identity: 'btn-disabled',
          page_version: 1
        }
      },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    };

    const res = executor.executeAction(intent);
    expect(res.status).toBe('TARGET_DISABLED');
  });

  it('executes TYPE into text input updating value and firing input/change events', () => {
    const input = document.getElementById('username-input') as HTMLInputElement;
    const inputSpy = vi.fn();
    input.addEventListener('input', inputSpy);

    const intent: ActionIntent = {
      action_id: 'act_type_1',
      type: 'TYPE',
      target: {
        world_element_ref: {
          page_id: 'page_1',
          observation_id: 'obs_1',
          element_id: 'elem_input_1',
          page_version: 1
        }
      },
      parameters: {
        text: ' Smith'
      },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    };

    const res = executor.executeAction(intent);
    expect(res.status).toBe('SUCCESS');
    expect(input.value).toBe('Alice Smith');
    expect(inputSpy).toHaveBeenCalled();
  });

  it('executes CLEAR_INPUT on input field', () => {
    const input = document.getElementById('username-input') as HTMLInputElement;

    const intent: ActionIntent = {
      action_id: 'act_clear_1',
      type: 'CLEAR_INPUT',
      target: {
        world_element_ref: {
          page_id: 'page_1',
          observation_id: 'obs_1',
          element_id: 'elem_input_1',
          page_version: 1
        }
      },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    };

    const res = executor.executeAction(intent);
    expect(res.status).toBe('SUCCESS');
    expect(input.value).toBe('');
  });

  it('executes SELECT by matching option value', () => {
    const select = document.getElementById('country-select') as HTMLSelectElement;

    const intent: ActionIntent = {
      action_id: 'act_select_1',
      type: 'SELECT',
      target: {
        world_element_ref: {
          page_id: 'page_1',
          observation_id: 'obs_1',
          element_id: 'elem_select_1',
          page_version: 1
        }
      },
      parameters: {
        value: 'CA'
      },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    };

    const res = executor.executeAction(intent);
    expect(res.status).toBe('SUCCESS');
    expect(select.value).toBe('CA');
  });

  it('executes CHECK and UNCHECK with strict idempotency', () => {
    const check1 = document.getElementById('terms-check') as HTMLInputElement;
    const check2 = document.getElementById('newsletter-check') as HTMLInputElement;

    // 1. CHECK unchecked box -> SUCCESS (becomes checked)
    const resCheck = executor.executeAction({
      action_id: 'act_chk_1',
      type: 'CHECK',
      target: { world_element_ref: { page_id: 'p1', observation_id: 'o1', element_id: 'elem_check_1', page_version: 1 } },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    });
    expect(resCheck.status).toBe('SUCCESS');
    expect(check1.checked).toBe(true);

    // 2. CHECK already checked box -> NO_OP
    const resCheckAgain = executor.executeAction({
      action_id: 'act_chk_2',
      type: 'CHECK',
      target: { world_element_ref: { page_id: 'p1', observation_id: 'o1', element_id: 'elem_check_1', page_version: 1 } },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    });
    expect(resCheckAgain.status).toBe('NO_OP');

    // 3. UNCHECK already unchecked box -> NO_OP
    const resUncheck = executor.executeAction({
      action_id: 'act_unchk_1',
      type: 'UNCHECK',
      target: { world_element_ref: { page_id: 'p1', observation_id: 'o1', element_id: 'elem_news', stable_dom_identity: 'newsletter-check', page_version: 1 } },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    });
    expect(resUncheck.status).toBe('SUCCESS');
    expect(check2.checked).toBe(false);

    const resUncheckAgain = executor.executeAction({
      action_id: 'act_unchk_2',
      type: 'UNCHECK',
      target: { world_element_ref: { page_id: 'p1', observation_id: 'o1', element_id: 'elem_news', stable_dom_identity: 'newsletter-check', page_version: 1 } },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    });
    expect(resUncheckAgain.status).toBe('NO_OP');
  });

  it('dispatches allowed KEY_PRESS and blocks disallowed keys', () => {
    const resAllowed = executor.executeAction({
      action_id: 'act_key_1',
      type: 'KEY_PRESS',
      parameters: { key: 'Enter' },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    });
    expect(resAllowed.status).toBe('SUCCESS');

    const resBlocked = executor.executeAction({
      action_id: 'act_key_bad',
      type: 'KEY_PRESS',
      parameters: { key: 'F12' },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    });
    expect(resBlocked.status).toBe('BLOCKED');
  });

  it('returns WOULD_EXECUTE in dry_run mode without modifying DOM', () => {
    const input = document.getElementById('username-input') as HTMLInputElement;

    const res = executor.executeAction({
      action_id: 'act_dry_run',
      type: 'CLEAR_INPUT',
      target: { world_element_ref: { page_id: 'p1', observation_id: 'o1', element_id: 'elem_input_1', page_version: 1 } },
      parameters: { dry_run: true },
      world_model_version: 1,
      page_version: 1,
      created_at: new Date().toISOString()
    });

    expect(res.status).toBe('WOULD_EXECUTE');
    expect(input.value).toBe('Alice'); // Unchanged
  });
});
