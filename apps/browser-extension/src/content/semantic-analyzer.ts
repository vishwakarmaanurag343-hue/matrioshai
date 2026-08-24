/**
 * MATRIOSHAI Semantic Page & Accessibility Intelligence Analyzer (Phase 5)
 *
 * Transforms the live web page DOM and PageObservation into a rich, strongly-typed
 * SemanticPageModel. Computes ARIA/HTML roles, accessible names, descriptions,
 * label relationships, component groupings (forms, radios, tabs, dialogs, tables, lists),
 * and multi-key semantic search indexes.
 */

import {
  type SemanticPageModel,
  type SemanticElement,
  type SemanticConfidence,
  type SemanticSource,
  type ControlClassification,
  type FormSemanticGroup,
  type RadioSemanticGroup,
  type TabSemanticGroup,
  type DialogSemanticGroup,
  type TableSemanticGroup,
  type ListSemanticGroup,
  type SemanticHeading,
  type SemanticLandmark,
  type SemanticPageIndexes,
  type BoundingBox
} from '../shared/types';

export class SemanticPageAnalyzer {
  private elementCounter = 0;
  private currentModelVersion = 1;
  private lastSemanticModel: SemanticPageModel | null = null;

  public getModelVersion(): number {
    return this.currentModelVersion;
  }

  public incrementModelVersion(): void {
    this.currentModelVersion++;
    if (this.lastSemanticModel) {
      this.lastSemanticModel.is_stale = true;
    }
  }

  public invalidateModel(): void {
    this.incrementModelVersion();
    this.lastSemanticModel = null;
  }

  public getLastModel(): SemanticPageModel | null {
    return this.lastSemanticModel;
  }

  /**
   * Analyze the live document and build a comprehensive SemanticPageModel
   */
  public analyzePage(tabId: number = 0, observationId?: string): SemanticPageModel {
    this.elementCounter = 0;
    const semanticModelId = `sem_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const obsId = observationId || `obs_linked_${Date.now()}`;

    const interactiveElements = this.extractSemanticElements();
    const headings = this.extractSemanticHeadings();
    const landmarks = this.extractSemanticLandmarks(interactiveElements);
    const forms = this.extractFormGroups(interactiveElements);
    const radioGroups = this.extractRadioGroups(interactiveElements);
    const tabs = this.extractTabGroups(interactiveElements);
    const dialogs = this.extractDialogGroups(interactiveElements);
    const tables = this.extractTableGroups();
    const lists = this.extractListGroups();

    const indexes = this.buildIndexes(interactiveElements, headings);
    const debugTree = this.buildDebugTree(landmarks, headings, forms, interactiveElements);

    const model: SemanticPageModel = {
      semantic_model_id: semanticModelId,
      model_version: this.currentModelVersion,
      observation_id: obsId,
      tab_id: tabId,
      is_stale: false,
      timestamp: new Date().toISOString(),
      page: {
        url: window.location.href,
        title: document.title || '',
        language: document.documentElement.lang || 'en'
      },
      landmarks,
      headings,
      interactive_elements: interactiveElements,
      forms,
      radio_groups: radioGroups,
      tabs,
      dialogs,
      tables,
      lists,
      indexes,
      debug_tree: debugTree,
      metadata: {
        total_interactive: interactiveElements.length,
        total_forms: forms.length,
        total_headings: headings.length
      }
    };

    this.lastSemanticModel = model;
    return model;
  }

  // ========================================================================
  // ACCESSIBILITY & ROLE COMPUTATION
  // ========================================================================

  private extractSemanticElements(): SemanticElement[] {
    const semanticElements: SemanticElement[] = [];
    const selector = [
      'a[href]',
      'button',
      'input:not([type="hidden"])',
      'textarea',
      'select',
      '[role="button"]',
      '[role="link"]',
      '[role="checkbox"]',
      '[role="radio"]',
      '[role="combobox"]',
      '[role="listbox"]',
      '[role="option"]',
      '[role="tab"]',
      '[role="menuitem"]',
      '[role="slider"]',
      '[role="switch"]',
      '[tabindex]:not([tabindex="-1"])',
      '[onclick]'
    ].join(', ');

    const nodes = document.querySelectorAll(selector);

    for (const raw of Array.from(nodes)) {
      const el = raw as HTMLElement;
      if (!this.isElementVisible(el)) continue;

      const elementId = this.assignElementId(el);
      const tagName = el.tagName.toLowerCase();
      const { role, source } = this.computeRole(el);
      const { name, nameSource } = this.computeAccessibleName(el);
      const description = this.computeAccessibleDescription(el);
      const semanticType = this.classifyControl(el, role);
      const isSensitive = this.detectSensitiveField(el, semanticType);

      const isEnabled = !(el as HTMLButtonElement).disabled && el.getAttribute('aria-disabled') !== 'true';
      const isFocused = document.activeElement === el;
      const isRequired = el.hasAttribute('required') || el.getAttribute('aria-required') === 'true';
      const isReadonly = el.hasAttribute('readonly') || el.getAttribute('aria-readonly') === 'true';

      let isSelected = el.getAttribute('aria-selected') === 'true';
      let isChecked = (el as HTMLInputElement).checked || el.getAttribute('aria-checked') === 'true';
      let expanded: boolean | null = null;
      if (el.hasAttribute('aria-expanded')) {
        expanded = el.getAttribute('aria-expanded') === 'true';
      }

      const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { x: 0, y: 0, width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 };
      const boundingBox: BoundingBox = {
        x: Math.round(rect.x || 0),
        y: Math.round(rect.y || 0),
        width: Math.round(rect.width || 0),
        height: Math.round(rect.height || 0),
        top: Math.round(rect.top || 0),
        left: Math.round(rect.left || 0),
        right: Math.round(rect.right || 0),
        bottom: Math.round(rect.bottom || 0)
      };

      // Relationship tracking
      const labelledBy = el.getAttribute('aria-labelledby') || this.findAssociatedLabelId(el);
      const describedBy = el.getAttribute('aria-describedby') || null;
      const controls = el.getAttribute('aria-controls') || null;

      const attributes: Record<string, string> = {};
      if (el.id) attributes.id = el.id;
      if (el.getAttribute('name')) attributes.name = el.getAttribute('name')!;
      if (el.getAttribute('type')) attributes.type = el.getAttribute('type')!;
      if (el.getAttribute('placeholder')) attributes.placeholder = el.getAttribute('placeholder')!;
      if (el.getAttribute('href')) attributes.href = el.getAttribute('href')!;

      // Confidence computation
      let confidence: SemanticConfidence = 'HIGH';
      if (source === 'heuristic' || nameSource === 'heuristic') {
        confidence = 'LOW';
      } else if (source === 'aria' || source === 'label') {
        confidence = 'HIGH';
      }

      // Safe value preview (NEVER expose sensitive values)
      let valuePreview: string | null = null;
      if (!isSensitive && (tagName === 'input' || tagName === 'textarea' || tagName === 'select')) {
        const val = (el as HTMLInputElement).value;
        if (val && typeof val === 'string') {
          valuePreview = val.slice(0, 50);
        }
      }

      semanticElements.push({
        element_id: elementId,
        role,
        name,
        description,
        tag_name: tagName,
        semantic_type: semanticType,
        source,
        confidence,
        visible: true,
        enabled: isEnabled,
        focused: isFocused,
        required: isRequired,
        readonly: isReadonly,
        selected: isSelected,
        checked: isChecked,
        expanded,
        sensitive: isSensitive,
        value_available: !isSensitive && (tagName === 'input' || tagName === 'textarea' || tagName === 'select'),
        value_preview: valuePreview,
        bounding_box: boundingBox,
        child_ids: [],
        relationships: {
          labelled_by: labelledBy,
          described_by: describedBy,
          controls
        },
        attributes
      });

      if (semanticElements.length >= 200) break;
    }

    return semanticElements;
  }

  private computeRole(el: HTMLElement): { role: string; source: SemanticSource } {
    const ariaRole = el.getAttribute('role')?.trim().toLowerCase();
    if (ariaRole && this.isValidAriaRole(ariaRole)) {
      return { role: ariaRole, source: 'aria' };
    }

    const tagName = el.tagName.toLowerCase();
    switch (tagName) {
      case 'a':
        return { role: el.getAttribute('href') ? 'link' : 'generic', source: 'native_html' };
      case 'button':
        return { role: 'button', source: 'native_html' };
      case 'input': {
        const type = (el as HTMLInputElement).type?.toLowerCase() || 'text';
        if (type === 'checkbox') return { role: 'checkbox', source: 'native_html' };
        if (type === 'radio') return { role: 'radio', source: 'native_html' };
        if (type === 'submit' || type === 'button' || type === 'reset' || type === 'image') return { role: 'button', source: 'native_html' };
        if (type === 'range') return { role: 'slider', source: 'native_html' };
        if (type === 'number') return { role: 'spinbutton', source: 'native_html' };
        return { role: 'textbox', source: 'native_html' };
      }
      case 'textarea':
        return { role: 'textbox', source: 'native_html' };
      case 'select':
        return { role: 'combobox', source: 'native_html' };
      case 'dialog':
        return { role: 'dialog', source: 'native_html' };
      default:
        return { role: 'widget', source: 'heuristic' };
    }
  }

  private isValidAriaRole(role: string): boolean {
    const validRoles = new Set([
      'button', 'link', 'textbox', 'checkbox', 'radio', 'combobox', 'listbox',
      'option', 'slider', 'spinbutton', 'tab', 'tabpanel', 'menu', 'menuitem',
      'dialog', 'alertdialog', 'heading', 'navigation', 'main', 'banner',
      'contentinfo', 'form', 'table', 'row', 'cell', 'search', 'region', 'switch'
    ]);
    return validRoles.has(role);
  }

  // ========================================================================
  // ACCESSIBLE NAME & DESCRIPTION COMPUTATION
  // ========================================================================

  private computeAccessibleName(el: HTMLElement): { name: string; nameSource: SemanticSource } {
    // 1. aria-labelledby
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      const ids = labelledBy.split(/\s+/);
      const textParts = ids
        .map((id) => document.getElementById(id)?.innerText?.trim())
        .filter(Boolean);
      if (textParts.length > 0) {
        return { name: textParts.join(' ').replace(/\s+/g, ' '), nameSource: 'aria' };
      }
    }

    // 2. aria-label
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel && ariaLabel.trim()) {
      return { name: ariaLabel.trim(), nameSource: 'aria' };
    }

    // 3. Associated <label for="id">
    if (el.id) {
      const labelEl = document.querySelector(`label[for="${el.id}"]`) as HTMLElement;
      if (labelEl && labelEl.innerText && labelEl.innerText.trim()) {
        return { name: labelEl.innerText.replace(/\s+/g, ' ').trim(), nameSource: 'label' };
      }
    }

    // 4. Enclosing parent <label>
    const parentLabel = el.closest('label');
    if (parentLabel && parentLabel.innerText && parentLabel.innerText.trim()) {
      const clone = parentLabel.cloneNode(true) as HTMLElement;
      const inputs = clone.querySelectorAll('input, select, textarea, button');
      inputs.forEach((i) => i.remove());
      const labelText = clone.innerText?.replace(/\s+/g, ' ').trim();
      if (labelText) {
        return { name: labelText, nameSource: 'label' };
      }
    }

    // 5. Meaningful Direct Text / Value
    const tagName = el.tagName.toLowerCase();
    if (tagName === 'button' || tagName === 'a' || el.getAttribute('role') === 'button') {
      const text = el.innerText?.replace(/\s+/g, ' ').trim();
      if (text) {
        return { name: text, nameSource: 'native_html' };
      }
    }

    if (tagName === 'input') {
      const inputEl = el as HTMLInputElement;
      if (inputEl.type === 'button' || inputEl.type === 'submit' || inputEl.type === 'reset') {
        if (inputEl.value && inputEl.value.trim()) {
          return { name: inputEl.value.trim(), nameSource: 'native_html' };
        }
      }
    }

    // 6. Placeholder
    const placeholder = el.getAttribute('placeholder');
    if (placeholder && placeholder.trim()) {
      return { name: placeholder.trim(), nameSource: 'heuristic' };
    }

    // 7. Title / Alt
    const title = el.getAttribute('title');
    if (title && title.trim()) {
      return { name: title.trim(), nameSource: 'heuristic' };
    }
    const alt = el.getAttribute('alt');
    if (alt && alt.trim()) {
      return { name: alt.trim(), nameSource: 'heuristic' };
    }

    return { name: '', nameSource: 'heuristic' };
  }

  private computeAccessibleDescription(el: HTMLElement): string | null {
    const describedBy = el.getAttribute('aria-describedby');
    if (describedBy) {
      const ids = describedBy.split(/\s+/);
      const textParts = ids
        .map((id) => document.getElementById(id)?.innerText?.trim())
        .filter(Boolean);
      if (textParts.length > 0) {
        return textParts.join(' ').replace(/\s+/g, ' ');
      }
    }
    return null;
  }

  private findAssociatedLabelId(el: HTMLElement): string | null {
    if (el.id) {
      const label = document.querySelector(`label[for="${el.id}"]`);
      if (label && label.id) return label.id;
    }
    return null;
  }

  // ========================================================================
  // CLASSIFICATION & PRIVACY FILTERING
  // ========================================================================

  private classifyControl(el: HTMLElement, role: string): ControlClassification {
    const tagName = el.tagName.toLowerCase();
    if (tagName === 'a') return 'LINK';
    if (tagName === 'button' || role === 'button') {
      if ((el as HTMLButtonElement).type === 'submit' || el.getAttribute('type') === 'submit') {
        return 'SUBMIT';
      }
      return 'BUTTON';
    }
    if (tagName === 'textarea') return 'TEXTAREA';
    if (tagName === 'select') return 'SELECT';
    if (role === 'combobox') return 'COMBOBOX';
    if (role === 'tab') return 'TAB';
    if (role === 'menuitem') return 'MENUITEM';
    if (role === 'option') return 'OPTION';

    if (tagName === 'input') {
      const type = (el as HTMLInputElement).type?.toLowerCase() || 'text';
      switch (type) {
        case 'email': return 'EMAIL';
        case 'password': return 'PASSWORD';
        case 'tel': return 'PHONE';
        case 'number': return 'NUMBER';
        case 'date': return 'DATE';
        case 'time': return 'TIME';
        case 'datetime-local': return 'DATETIME';
        case 'url': return 'URL';
        case 'search': return 'SEARCH';
        case 'checkbox': return 'CHECKBOX';
        case 'radio': return 'RADIO';
        case 'file': return 'FILE';
        case 'range': return 'RANGE';
        case 'submit': return 'SUBMIT';
        case 'button': return 'BUTTON';
        default: return 'TEXT';
      }
    }

    return 'UNKNOWN';
  }

  private detectSensitiveField(el: HTMLElement, classification: ControlClassification): boolean {
    if (classification === 'PASSWORD') return true;
    const name = (el.getAttribute('name') || '').toLowerCase();
    const id = (el.id || '').toLowerCase();
    const autocomplete = (el.getAttribute('autocomplete') || '').toLowerCase();

    const sensitiveKeywords = ['password', 'passwd', 'cvv', 'cvc', 'creditcard', 'cardnumber', 'token', 'secret', 'ssn', 'pin'];
    for (const kw of sensitiveKeywords) {
      if (name.includes(kw) || id.includes(kw) || autocomplete.includes(kw)) {
        return true;
      }
    }
    return false;
  }

  // ========================================================================
  // COMPONENT GROUPING (FORMS, RADIOS, TABS, DIALOGS, TABLES, LISTS)
  // ========================================================================

  private extractFormGroups(elements: SemanticElement[]): FormSemanticGroup[] {
    const forms: FormSemanticGroup[] = [];
    const formNodes = document.querySelectorAll('form, [role="form"]');

    for (const formNode of Array.from(formNodes)) {
      const formEl = formNode as HTMLElement;
      const formId = formEl.id || this.assignElementId(formEl);
      const name = formEl.getAttribute('aria-label') || formEl.getAttribute('name') || formEl.id || 'Form';
      const action = formEl.getAttribute('action') || null;
      const method = formEl.getAttribute('method')?.toUpperCase() || 'GET';

      const fieldIds: string[] = [];
      const submitButtonIds: string[] = [];
      const requiredFieldIds: string[] = [];

      for (const el of elements) {
        const domEl = document.querySelector(`[data-matrioshai-id="${el.element_id}"]`);
        if (domEl && formEl.contains(domEl)) {
          el.parent_id = formId;
          fieldIds.push(el.element_id);
          if (el.semantic_type === 'SUBMIT' || (el.role === 'button' && el.name.toLowerCase().includes('search'))) {
            submitButtonIds.push(el.element_id);
          }
          if (el.required) {
            requiredFieldIds.push(el.element_id);
          }
        }
      }

      forms.push({
        form_id: formId,
        name,
        action,
        method,
        field_ids: fieldIds,
        submit_button_ids: submitButtonIds,
        required_field_ids: requiredFieldIds
      });
    }

    return forms;
  }

  private extractRadioGroups(elements: SemanticElement[]): RadioSemanticGroup[] {
    const groups: Map<string, RadioSemanticGroup> = new Map();

    for (const el of elements) {
      if (el.role === 'radio' || el.semantic_type === 'RADIO') {
        const domEl = document.querySelector(`[data-matrioshai-id="${el.element_id}"]`);
        const groupName = domEl?.getAttribute('name') || 'default_radio_group';

        if (!groups.has(groupName)) {
          const fieldset = domEl?.closest('fieldset');
          const legend = fieldset?.querySelector('legend')?.innerText?.trim();
          groups.set(groupName, {
            group_name: groupName,
            label: legend || groupName,
            selected_element_id: null,
            options: []
          });
        }

        const group = groups.get(groupName)!;
        group.options.push({
          element_id: el.element_id,
          name: el.name || 'Option',
          selected: el.checked || el.selected,
          disabled: !el.enabled
        });

        if (el.checked || el.selected) {
          group.selected_element_id = el.element_id;
        }
      }
    }

    return Array.from(groups.values());
  }

  private extractTabGroups(elements: SemanticElement[]): TabSemanticGroup[] {
    const tabGroups: TabSemanticGroup[] = [];
    const tabLists = document.querySelectorAll('[role="tablist"]');

    if (tabLists.length > 0) {
      for (const tl of Array.from(tabLists)) {
        const tabListEl = tl as HTMLElement;
        const tabs: TabSemanticGroup['tabs'] = [];

        for (const el of elements) {
          if (el.role === 'tab') {
            const domEl = document.querySelector(`[data-matrioshai-id="${el.element_id}"]`);
            if (domEl && tabListEl.contains(domEl)) {
              tabs.push({
                element_id: el.element_id,
                name: el.name,
                selected: el.selected,
                controls_panel_id: el.relationships.controls
              });
            }
          }
        }

        if (tabs.length > 0) {
          tabGroups.push({
            tab_list_id: tabListEl.id || null,
            tabs
          });
        }
      }
    } else {
      // Fallback: Group any solitary role="tab" elements
      const tabs = elements.filter((e) => e.role === 'tab').map((e) => ({
        element_id: e.element_id,
        name: e.name,
        selected: e.selected,
        controls_panel_id: e.relationships.controls
      }));
      if (tabs.length > 0) {
        tabGroups.push({ tab_list_id: null, tabs });
      }
    }

    return tabGroups;
  }

  private extractDialogGroups(elements: SemanticElement[]): DialogSemanticGroup[] {
    const dialogs: DialogSemanticGroup[] = [];
    const dialogNodes = document.querySelectorAll('dialog, [role="dialog"], [role="alertdialog"]');

    for (const d of Array.from(dialogNodes)) {
      const dEl = d as HTMLElement;
      const role = (dEl.getAttribute('role') === 'alertdialog' ? 'alertdialog' : 'dialog') as 'dialog' | 'alertdialog';
      const name = dEl.getAttribute('aria-label') || dEl.querySelector('h1, h2, h3, h4')?.textContent?.trim() || 'Dialog';
      const isVisible = this.isElementVisible(dEl);

      const interactiveIds: string[] = [];
      for (const el of elements) {
        const domEl = document.querySelector(`[data-matrioshai-id="${el.element_id}"]`);
        if (domEl && dEl.contains(domEl)) {
          interactiveIds.push(el.element_id);
        }
      }

      dialogs.push({
        dialog_id: dEl.id || this.assignElementId(dEl),
        name,
        role,
        visible: isVisible,
        interactive_element_ids: interactiveIds
      });
    }

    return dialogs;
  }

  private extractTableGroups(): TableSemanticGroup[] {
    const tables: TableSemanticGroup[] = [];
    const tableNodes = document.querySelectorAll('table, [role="table"]');

    for (const t of Array.from(tableNodes)) {
      const tEl = t as HTMLElement;
      const name = tEl.getAttribute('aria-label') || tEl.querySelector('caption')?.innerText?.trim() || null;
      const headers: string[] = [];
      const thNodes = tEl.querySelectorAll('th, [role="columnheader"]');
      thNodes.forEach((th) => headers.push(th.textContent?.trim() || ''));

      const rows: TableSemanticGroup['rows'] = [];
      const trNodes = Array.from(tEl.querySelectorAll('tr, [role="row"]'));

      // Filter out pure header rows if they are already in thead
      const dataRows = trNodes.filter((tr) => {
        const hasTd = tr.querySelector('td, [role="cell"]');
        return hasTd !== null || !tr.closest('thead');
      });

      dataRows.forEach((tr, rIdx) => {
        const rowCells: TableSemanticGroup['rows'][0] = [];
        const cells = tr.querySelectorAll('td, th, [role="cell"], [role="columnheader"]');
        cells.forEach((c, cIdx) => {
          rowCells.push({
            text: c.textContent?.trim() || '',
            is_header: c.tagName.toLowerCase() === 'th' || c.getAttribute('role') === 'columnheader',
            row_index: rIdx,
            col_index: cIdx
          });
        });
        if (rowCells.length > 0) rows.push(rowCells);
      });

      tables.push({
        table_id: tEl.id || this.assignElementId(tEl),
        name,
        headers,
        row_count: rows.length,
        col_count: headers.length || (rows[0]?.length || 0),
        rows: rows.slice(0, 50)
      });
    }

    return tables;
  }

  private extractListGroups(): ListSemanticGroup[] {
    const lists: ListSemanticGroup[] = [];
    const listNodes = document.querySelectorAll('ul, ol, [role="list"]');

    for (const l of Array.from(listNodes)) {
      const lEl = l as HTMLElement;
      if (!this.isElementVisible(lEl)) continue;

      const type = lEl.tagName.toLowerCase() === 'ol' ? 'ordered' : 'unordered';
      const name = lEl.getAttribute('aria-label') || null;
      const items: string[] = [];

      const liNodes = lEl.querySelectorAll(':scope > li, [role="listitem"]');
      liNodes.forEach((li) => {
        const text = li.textContent?.replace(/\s+/g, ' ').trim();
        if (text) items.push(text.slice(0, 100));
      });

      if (items.length > 0) {
        lists.push({
          list_id: lEl.id || this.assignElementId(lEl),
          type,
          name,
          item_count: items.length,
          items: items.slice(0, 50)
        });
        if (lists.length >= 20) break;
      }
    }

    return lists;
  }

  private extractSemanticHeadings(): SemanticHeading[] {
    const headings: SemanticHeading[] = [];
    const nodes = document.querySelectorAll('h1, h2, h3, h4, h5, h6, [role="heading"]');

    for (const n of Array.from(nodes)) {
      const el = n as HTMLElement;
      if (!this.isElementVisible(el)) continue;

      let level = 1;
      if (el.tagName.startsWith('H') || el.tagName.startsWith('h')) {
        level = parseInt(el.tagName.substring(1), 10) || 1;
      } else if (el.hasAttribute('aria-level')) {
        level = parseInt(el.getAttribute('aria-level')!, 10) || 1;
      }

      const text = el.innerText?.replace(/\s+/g, ' ').trim() || '';
      if (text) {
        headings.push({
          level,
          text,
          element_id: el.id || this.assignElementId(el)
        });
      }
    }

    return headings;
  }

  private extractSemanticLandmarks(elements: SemanticElement[]): SemanticLandmark[] {
    const landmarks: SemanticLandmark[] = [];
    const selector = 'header, nav, main, footer, article, section, aside, [role="banner"], [role="navigation"], [role="main"], [role="contentinfo"], [role="search"], [role="complementary"]';
    const nodes = document.querySelectorAll(selector);

    for (const n of Array.from(nodes)) {
      const el = n as HTMLElement;
      if (!this.isElementVisible(el)) continue;

      const role = el.getAttribute('role') || el.tagName.toLowerCase();
      const label = el.getAttribute('aria-label') || el.getAttribute('title') || null;

      const childElementIds: string[] = [];
      for (const se of elements) {
        const domEl = document.querySelector(`[data-matrioshai-id="${se.element_id}"]`);
        if (domEl && el.contains(domEl)) {
          childElementIds.push(se.element_id);
        }
      }

      landmarks.push({
        role,
        tag_name: el.tagName.toLowerCase(),
        label,
        element_ids: childElementIds
      });
      if (landmarks.length >= 25) break;
    }

    return landmarks;
  }

  // ========================================================================
  // INDEXING & DETERMINISTIC TREE
  // ========================================================================

  private buildIndexes(elements: SemanticElement[], headings: SemanticHeading[]): SemanticPageIndexes {
    const indexes: SemanticPageIndexes = {
      byRole: {},
      byName: {},
      byLabel: {},
      byId: {},
      byTag: {},
      byType: {}
    };

    for (const h of headings) {
      if (!indexes.byRole['heading']) indexes.byRole['heading'] = [];
      indexes.byRole['heading'].push(h.element_id);
      if (h.text) {
        const n = h.text.toLowerCase().trim();
        if (!indexes.byName[n]) indexes.byName[n] = [];
        indexes.byName[n].push(h.element_id);
      }
      indexes.byId[h.element_id] = h.element_id;
    }

    for (const el of elements) {
      // byRole
      const r = el.role.toLowerCase();
      if (!indexes.byRole[r]) indexes.byRole[r] = [];
      indexes.byRole[r].push(el.element_id);

      // byName
      if (el.name) {
        const n = el.name.toLowerCase().trim();
        if (!indexes.byName[n]) indexes.byName[n] = [];
        indexes.byName[n].push(el.element_id);
      }

      // byLabel
      if (el.relationships.labelled_by) {
        const l = el.relationships.labelled_by.toLowerCase();
        if (!indexes.byLabel[l]) indexes.byLabel[l] = [];
        indexes.byLabel[l].push(el.element_id);
      }
      if (el.name) {
        const n = el.name.toLowerCase().trim();
        if (!indexes.byLabel[n]) indexes.byLabel[n] = [];
        indexes.byLabel[n].push(el.element_id);
      }

      // byId
      indexes.byId[el.element_id] = el.element_id;
      if (el.attributes.id) {
        indexes.byId[el.attributes.id] = el.element_id;
      }

      // byTag
      const t = el.tag_name.toLowerCase();
      if (!indexes.byTag[t]) indexes.byTag[t] = [];
      indexes.byTag[t].push(el.element_id);

      // byType
      const st = el.semantic_type.toLowerCase();
      if (!indexes.byType[st]) indexes.byType[st] = [];
      indexes.byType[st].push(el.element_id);
    }

    return indexes;
  }

  private buildDebugTree(
    landmarks: SemanticLandmark[],
    headings: SemanticHeading[],
    forms: FormSemanticGroup[],
    elements: SemanticElement[]
  ): string {
    const lines: string[] = [];
    lines.push(`PAGE: ${document.title || window.location.href}`);

    if (headings.length > 0) {
      lines.push('  HEADINGS:');
      headings.slice(0, 5).forEach((h) => lines.push(`    H${h.level}: "${h.text}"`));
    }

    if (landmarks.length > 0) {
      lines.push('  LANDMARKS:');
      landmarks.slice(0, 5).forEach((l) => lines.push(`    ${l.role}${l.label ? ` (${l.label})` : ''}`));
    }

    if (forms.length > 0) {
      lines.push('  FORMS:');
      forms.forEach((f) => {
        lines.push(`    Form: "${f.name}" (${f.field_ids.length} fields, ${f.submit_button_ids.length} submits)`);
      });
    }

    lines.push(`  INTERACTIVE ELEMENTS (${elements.length}):`);
    elements.slice(0, 15).forEach((el) => {
      lines.push(`    [${el.element_id}] ${el.role.toUpperCase()}: "${el.name}" (type=${el.semantic_type}, enabled=${el.enabled})`);
    });

    return lines.join('\n');
  }

  private assignElementId(el: HTMLElement): string {
    const existing = el.getAttribute('data-matrioshai-id');
    if (existing) return existing;

    const id = `el_${this.elementCounter++}`;
    el.setAttribute('data-matrioshai-id', id);
    return id;
  }

  private isElementVisible(el: HTMLElement): boolean {
    if (typeof window.getComputedStyle === 'undefined') return true;
    try {
      const style = window.getComputedStyle(el);
      if (style.display === 'none') return false;
      if (style.visibility === 'hidden' || style.visibility === 'collapse') return false;
      if (parseFloat(style.opacity) <= 0) return false;
      return true;
    } catch {
      return true;
    }
  }
}

export const semanticPageAnalyzer = new SemanticPageAnalyzer();
