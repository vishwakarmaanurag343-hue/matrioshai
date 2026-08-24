import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

describe('MATRIOSHAI Chrome Extension Manifest V3 Validation', () => {
  const manifestPath = path.resolve(__dirname, '../../manifest.json');

  it('manifest.json exists and is valid JSON', () => {
    expect(fs.existsSync(manifestPath)).toBe(true);
    const content = fs.readFileSync(manifestPath, 'utf-8');
    const parsed = JSON.parse(content);
    expect(parsed).toBeDefined();
  });

  it('declares manifest_version 3', () => {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    expect(manifest.manifest_version).toBe(3);
    expect(manifest.name).toBe('MATRIOSHAI Browser Agent');
    expect(manifest.version).toBe('0.1.0');
  });

  it('defines service worker background script as module', () => {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    expect(manifest.background).toBeDefined();
    expect(manifest.background.service_worker).toBe('background.js');
    expect(manifest.background.type).toBe('module');
  });

  it('defines content script with document_idle run timing', () => {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    expect(manifest.content_scripts).toBeDefined();
    expect(Array.isArray(manifest.content_scripts)).toBe(true);
    expect(manifest.content_scripts[0].matches).toContain('<all_urls>');
    expect(manifest.content_scripts[0].js).toContain('content.js');
    expect(manifest.content_scripts[0].run_at).toBe('document_idle');
  });

  it('requests only minimal permissions for Phase 1', () => {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    expect(manifest.permissions).toBeDefined();
    expect(manifest.permissions).toContain('storage');
    expect(manifest.permissions).toContain('activeTab');
    // Ensure broad / high-risk permissions are NOT requested in Phase 1
    expect(manifest.permissions).not.toContain('webRequest');
    expect(manifest.permissions).not.toContain('debugger');
    expect(manifest.permissions).not.toContain('cookies');
    expect(manifest.permissions).not.toContain('declarativeNetRequest');
  });

  it('references valid existing PNG icons', () => {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    expect(manifest.icons).toBeDefined();
    expect(manifest.icons['16']).toBe('assets/icons/icon-16.png');
    expect(manifest.icons['48']).toBe('assets/icons/icon-48.png');
    expect(manifest.icons['128']).toBe('assets/icons/icon-128.png');

    const icon16 = path.resolve(__dirname, '../../', manifest.icons['16']);
    const icon48 = path.resolve(__dirname, '../../', manifest.icons['48']);
    const icon128 = path.resolve(__dirname, '../../', manifest.icons['128']);

    expect(fs.existsSync(icon16)).toBe(true);
    expect(fs.existsSync(icon48)).toBe(true);
    expect(fs.existsSync(icon128)).toBe(true);
  });
});
