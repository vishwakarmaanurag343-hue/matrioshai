import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Logger } from '../shared/logger';

describe('MATRIOSHAI Centralized Logger', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('prefixes logs with proper component scope tag', () => {
    const consoleSpy = vi.spyOn(console, 'info').mockImplementation(() => {});
    const logger = new Logger('SERVICE_WORKER', 'development');

    logger.info('Test service worker log');
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('[MATRIOSHAI][ServiceWorker][INFO] Test service worker log')
    );
  });

  it('filters debug logs in production mode', () => {
    const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
    const logger = new Logger('POPUP', 'production');

    logger.debug('Verbose debug message');
    expect(debugSpy).not.toHaveBeenCalled();
  });

  it('allows info/warn/error in production mode', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const logger = new Logger('CONTENT_SCRIPT', 'production');

    logger.error('Critical failure');
    expect(errorSpy).toHaveBeenCalledWith(
      expect.stringContaining('[MATRIOSHAI][ContentScript][ERROR] Critical failure')
    );
  });

  it('redacts sensitive bearer token patterns in strings', () => {
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});
    const logger = new Logger('EXTENSION', 'development');

    logger.info('Connecting with auth', 'Bearer secret_token_12345678');
    expect(infoSpy).toHaveBeenCalledWith(
      expect.stringContaining('[MATRIOSHAI][Extension][INFO] Connecting with auth'),
      'Bearer [REDACTED]'
    );
  });
});
