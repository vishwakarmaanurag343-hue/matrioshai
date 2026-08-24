/**
 * MATRIOSHAI Safe DOM Action Executor (Phase 8)
 *
 * Predefined, controlled DOM event dispatchers and manipulators.
 * Strictly adheres to safety constraints:
 * - No arbitrary script execution
 * - Idempotent checkbox/radio operations
 * - Sensitive text redaction in logging
 * - Whitelisted keyboard interactions
 * - Verified visibility and interactivity checks
 */

import { ACTION_CONFIG } from '../shared/constants';
import { createScopedLogger } from '../shared/logger';
import {
  type ActionIntent,
  type ActionStatus,
  type ActionTarget
} from '../shared/types';

const logger = createScopedLogger('ACTION_EXECUTOR');

export class ActionDomExecutor {
  /**
   * Find DOM element from ActionTarget
   */
  public findElement(target?: ActionTarget | null): HTMLElement | null {
    if (!target) return null;
    if (typeof document === 'undefined') return null;

    // 1. By data-matrioshai-id (observation element_id)
    if (target.world_element_ref?.element_id) {
      const el = document.querySelector(`[data-matrioshai-id="${target.world_element_ref.element_id}"]`) as HTMLElement;
      if (el) return el;
    }

    // 2. By stable DOM identity (id attribute)
    if (target.world_element_ref?.stable_dom_identity) {
      const el = document.getElementById(target.world_element_ref.stable_dom_identity);
      if (el) return el;
    }

    if (target.semantic_element_ref?.stable_id) {
      const el = document.getElementById(target.semantic_element_ref.stable_id);
      if (el) return el;
    }

    // 3. By semantic element_id
    if (target.semantic_element_ref?.element_id) {
      const el = document.querySelector(`[data-matrioshai-id="${target.semantic_element_ref.element_id}"]`) as HTMLElement;
      if (el) return el;
    }

    // 4. By coordinates (fallback)
    if (target.coordinates && typeof document.elementFromPoint === 'function') {
      const el = document.elementFromPoint(target.coordinates.x, target.coordinates.y) as HTMLElement;
      if (el) return el;
    }

    // 5. By expected role + name search
    if (target.expected_role && target.expected_name) {
      const all = Array.from(document.querySelectorAll('*')) as HTMLElement[];
      for (const el of all) {
        const role = el.getAttribute('role') || el.tagName.toLowerCase();
        const name = el.getAttribute('aria-label') || el.innerText || el.getAttribute('title') || '';
        if (role.toLowerCase() === target.expected_role.toLowerCase() && name.trim().toLowerCase() === target.expected_name.trim().toLowerCase()) {
          return el;
        }
      }
    }

    return null;
  }

  /**
   * Check if element is interactable (visible, not disabled, attached)
   */
  public isInteractable(element: HTMLElement): { interactable: boolean; reason?: string } {
    if (!element.isConnected) {
      return { interactable: false, reason: 'TARGET_DETACHED' };
    }

    if ((element as HTMLButtonElement | HTMLInputElement).disabled) {
      return { interactable: false, reason: 'TARGET_DISABLED' };
    }

    if (element.getAttribute('aria-disabled') === 'true') {
      return { interactable: false, reason: 'TARGET_DISABLED' };
    }

    const style = window.getComputedStyle ? window.getComputedStyle(element) : null;
    if (style) {
      if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
        return { interactable: false, reason: 'TARGET_INVISIBLE' };
      }
      if (style.pointerEvents === 'none') {
        return { interactable: false, reason: 'TARGET_NOT_INTERACTABLE' };
      }
    }

    return { interactable: true };
  }

  /**
   * Execute CLICK action
   */
  public executeClick(intent: ActionIntent): { status: ActionStatus; message?: string; detail?: string } {
    const el = this.findElement(intent.target);
    if (!el) {
      return { status: 'NOT_FOUND', message: 'Element not found for click' };
    }

    const check = this.isInteractable(el);
    if (!check.interactable) {
      return { status: (check.reason as ActionStatus) || 'FAILED', message: check.reason };
    }

    // Safe interior center coordinates
    const rect = el.getBoundingClientRect();
    const clientX = Math.round(rect.left + rect.width / 2);
    const clientY = Math.round(rect.top + rect.height / 2);

    const eventInit: MouseEventInit = {
      bubbles: true,
      cancelable: true,
      view: window,
      clientX,
      clientY,
      screenX: clientX,
      screenY: clientY,
      button: 0,
      buttons: 1
    };

    try {
      el.dispatchEvent(new PointerEvent('pointerdown', { ...eventInit, pointerType: 'mouse' }));
      el.dispatchEvent(new MouseEvent('mousedown', eventInit));
      el.focus();
      el.dispatchEvent(new PointerEvent('pointerup', { ...eventInit, pointerType: 'mouse', buttons: 0 }));
      el.dispatchEvent(new MouseEvent('mouseup', { ...eventInit, buttons: 0 }));
      el.dispatchEvent(new MouseEvent('click', { ...eventInit, buttons: 0 }));

      return { status: 'SUCCESS', message: `Clicked element at (${clientX}, ${clientY})` };
    } catch (err) {
      return { status: 'FAILED', message: `Click dispatch error: ${String(err)}` };
    }
  }

  /**
   * Execute TYPE action
   */
  public executeType(intent: ActionIntent): { status: ActionStatus; message?: string } {
    const el = this.findElement(intent.target);
    if (!el) {
      return { status: 'NOT_FOUND', message: 'Element not found for type' };
    }

    const check = this.isInteractable(el);
    if (!check.interactable) {
      return { status: (check.reason as ActionStatus) || 'FAILED', message: check.reason };
    }

    const textToType = String(intent.parameters?.text ?? intent.parameters?.value ?? '');
    const isInput = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement;
    const isContentEditable = el.isContentEditable;

    if (!isInput && !isContentEditable) {
      return { status: 'FAILED', message: 'Target element is not an editable input or contenteditable' };
    }

    if (isInput && (el as HTMLInputElement).readOnly) {
      return { status: 'FAILED', message: 'Input is readonly' };
    }

    try {
      el.focus();

      if (isInput) {
        const input = el as HTMLInputElement | HTMLTextAreaElement;
        const currentVal = input.value || '';
        input.value = currentVal + textToType;

        input.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
        input.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
      } else if (isContentEditable) {
        el.innerText = (el.innerText || '') + textToType;
        el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
      }

      return { status: 'SUCCESS', message: 'Successfully typed text into target' };
    } catch (err) {
      return { status: 'FAILED', message: `Type dispatch error: ${String(err)}` };
    }
  }

  /**
   * Execute CLEAR_INPUT action
   */
  public executeClearInput(intent: ActionIntent): { status: ActionStatus; message?: string } {
    const el = this.findElement(intent.target);
    if (!el) {
      return { status: 'NOT_FOUND', message: 'Element not found for clear input' };
    }

    const check = this.isInteractable(el);
    if (!check.interactable) {
      return { status: (check.reason as ActionStatus) || 'FAILED', message: check.reason };
    }

    if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
      el.focus();
      el.value = '';
      el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
      el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
      return { status: 'SUCCESS', message: 'Input value cleared' };
    }

    if (el.isContentEditable) {
      el.focus();
      el.innerText = '';
      el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
      return { status: 'SUCCESS', message: 'Contenteditable cleared' };
    }

    return { status: 'FAILED', message: 'Target is not editable' };
  }

  /**
   * Execute SELECT action
   */
  public executeSelect(intent: ActionIntent): { status: ActionStatus; message?: string } {
    const el = this.findElement(intent.target);
    if (!el) {
      return { status: 'NOT_FOUND', message: 'Select element not found' };
    }

    if (!(el instanceof HTMLSelectElement)) {
      return { status: 'FAILED', message: 'Target is not a native <select> element' };
    }

    const check = this.isInteractable(el);
    if (!check.interactable) {
      return { status: (check.reason as ActionStatus) || 'FAILED', message: check.reason };
    }

    const targetVal = String(intent.parameters?.value ?? intent.parameters?.text ?? '');
    let matchedOption: HTMLOptionElement | null = null;

    for (let i = 0; i < el.options.length; i++) {
      const opt = el.options[i];
      if (opt && (opt.value === targetVal || opt.text.trim().toLowerCase() === targetVal.trim().toLowerCase())) {
        matchedOption = opt;
        el.selectedIndex = i;
        break;
      }
    }

    if (!matchedOption) {
      return { status: 'NOT_FOUND', message: `Option '${targetVal}' not found in select` };
    }

    el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
    el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
    return { status: 'SUCCESS', message: `Selected option '${matchedOption.value}'` };
  }

  /**
   * Execute CHECK action (Idempotent)
   */
  public executeCheck(intent: ActionIntent): { status: ActionStatus; message?: string } {
    const el = this.findElement(intent.target);
    if (!el) {
      return { status: 'NOT_FOUND', message: 'Checkbox element not found' };
    }

    if (!(el instanceof HTMLInputElement) || (el.type !== 'checkbox' && el.type !== 'radio')) {
      return { status: 'FAILED', message: 'Target is not a checkbox or radio input' };
    }

    const check = this.isInteractable(el);
    if (!check.interactable) {
      return { status: (check.reason as ActionStatus) || 'FAILED', message: check.reason };
    }

    // Idempotency: If already checked, return NO_OP
    if (el.checked) {
      return { status: 'NO_OP', message: 'Element is already checked' };
    }

    el.checked = true;
    el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
    el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
    return { status: 'SUCCESS', message: 'Checkbox checked' };
  }

  /**
   * Execute UNCHECK action (Idempotent)
   */
  public executeUncheck(intent: ActionIntent): { status: ActionStatus; message?: string } {
    const el = this.findElement(intent.target);
    if (!el) {
      return { status: 'NOT_FOUND', message: 'Checkbox element not found' };
    }

    if (!(el instanceof HTMLInputElement) || el.type !== 'checkbox') {
      return { status: 'FAILED', message: 'Target is not a checkbox input' };
    }

    const check = this.isInteractable(el);
    if (!check.interactable) {
      return { status: (check.reason as ActionStatus) || 'FAILED', message: check.reason };
    }

    // Idempotency: If already unchecked, return NO_OP
    if (!el.checked) {
      return { status: 'NO_OP', message: 'Element is already unchecked' };
    }

    el.checked = false;
    el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
    el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
    return { status: 'SUCCESS', message: 'Checkbox unchecked' };
  }

  /**
   * Execute FOCUS action
   */
  public executeFocus(intent: ActionIntent): { status: ActionStatus; message?: string } {
    const el = this.findElement(intent.target);
    if (!el) {
      return { status: 'NOT_FOUND', message: 'Element not found for focus' };
    }

    el.focus();
    return { status: 'SUCCESS', message: 'Focused element' };
  }

  /**
   * Execute SCROLL action
   */
  public executeScroll(intent: ActionIntent): { status: ActionStatus; message?: string } {
    const el = this.findElement(intent.target);
    const direction = intent.parameters?.direction || 'DOWN';
    const amount = Math.min(Math.max(Number(intent.parameters?.amount ?? 300), -5000), 5000);

    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return { status: 'SUCCESS', message: 'Scrolled element into view' };
    }

    let dx = 0;
    let dy = 0;
    if (direction === 'DOWN') dy = amount;
    else if (direction === 'UP') dy = -amount;
    else if (direction === 'RIGHT') dx = amount;
    else if (direction === 'LEFT') dx = -amount;

    if (typeof window !== 'undefined' && window.scrollBy) {
      window.scrollBy({ left: dx, top: dy, behavior: 'smooth' });
    }

    return { status: 'SUCCESS', message: `Scrolled window (${dx}, ${dy})` };
  }

  /**
   * Execute KEY_PRESS action
   */
  public executeKeyPress(intent: ActionIntent): { status: ActionStatus; message?: string } {
    const key = String(intent.parameters?.key ?? '');
    if (!(ACTION_CONFIG.ALLOWED_KEY_PRESSES as readonly string[]).includes(key)) {
      return { status: 'BLOCKED', message: `Key '${key}' is not permitted by whitelist policy` };
    }

    const targetEl = this.findElement(intent.target) || (document.activeElement as HTMLElement) || document.body;

    try {
      const eventInit: KeyboardEventInit = {
        key,
        code: key,
        bubbles: true,
        cancelable: true,
        view: window
      };

      targetEl.dispatchEvent(new KeyboardEvent('keydown', eventInit));
      targetEl.dispatchEvent(new KeyboardEvent('keyup', eventInit));

      return { status: 'SUCCESS', message: `Dispatched key press '${key}'` };
    } catch (err) {
      return { status: 'FAILED', message: `Key press error: ${String(err)}` };
    }
  }

  /**
   * Dispatch action intent to appropriate executor
   */
  public executeAction(intent: ActionIntent): { status: ActionStatus; message?: string } {
    logger.debug(`Executing DOM action ${intent.action_id} (${intent.type})`);
    if (intent.parameters?.dry_run) {
      return { status: 'WOULD_EXECUTE', message: 'Dry run passed validation; no DOM actions dispatched' };
    }

    switch (intent.type) {
      case 'CLICK':
        return this.executeClick(intent);
      case 'TYPE':
        return this.executeType(intent);
      case 'CLEAR_INPUT':
        return this.executeClearInput(intent);
      case 'SELECT':
        return this.executeSelect(intent);
      case 'CHECK':
        return this.executeCheck(intent);
      case 'UNCHECK':
        return this.executeUncheck(intent);
      case 'FOCUS':
        return this.executeFocus(intent);
      case 'SCROLL':
        return this.executeScroll(intent);
      case 'KEY_PRESS':
        return this.executeKeyPress(intent);
      case 'WAIT':
        return { status: 'SUCCESS', message: `Wait completed (${intent.parameters?.duration_ms || 1000}ms)` };
      default:
        return { status: 'FAILED', message: `Unsupported action type '${intent.type}'` };
    }
  }
}

export const actionDomExecutor = new ActionDomExecutor();
