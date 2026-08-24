/**
 * MATRIOSHAI Centralized Logger (Phase 1)
 */

import { LOG_PREFIXES } from './constants';
import type { ExtensionEnvironment } from './types';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';
export type LogSource = keyof typeof LOG_PREFIXES;

const LEVEL_WEIGHTS: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40
};

export class Logger {
  private prefix: string;
  private environment: ExtensionEnvironment;
  private minLevel: LogLevel;

  constructor(source: LogSource = 'EXTENSION', environment: ExtensionEnvironment = 'development') {
    this.prefix = LOG_PREFIXES[source] || LOG_PREFIXES.EXTENSION;
    this.environment = environment;
    this.minLevel = environment === 'production' ? 'info' : 'debug';
  }

  public setEnvironment(env: ExtensionEnvironment): void {
    this.environment = env;
    this.minLevel = env === 'production' ? 'info' : 'debug';
  }

  public getEnvironment(): ExtensionEnvironment {
    return this.environment;
  }

  public setMinLevel(level: LogLevel): void {
    this.minLevel = level;
  }

  public debug(message: string, ...args: unknown[]): void {
    if (this.shouldLog('debug')) {
      console.debug(`${this.prefix}[DEBUG] ${message}`, ...this.sanitizeArgs(args));
    }
  }

  public info(message: string, ...args: unknown[]): void {
    if (this.shouldLog('info')) {
      console.info(`${this.prefix}[INFO] ${message}`, ...this.sanitizeArgs(args));
    }
  }

  public warn(message: string, ...args: unknown[]): void {
    if (this.shouldLog('warn')) {
      console.warn(`${this.prefix}[WARN] ${message}`, ...this.sanitizeArgs(args));
    }
  }

  public error(message: string, ...args: unknown[]): void {
    if (this.shouldLog('error')) {
      console.error(`${this.prefix}[ERROR] ${message}`, ...this.sanitizeArgs(args));
    }
  }

  private shouldLog(level: LogLevel): boolean {
    return LEVEL_WEIGHTS[level] >= LEVEL_WEIGHTS[this.minLevel];
  }

  private sanitizeArgs(args: unknown[]): unknown[] {
    return args.map((arg) => {
      if (typeof arg === 'string') {
        // Redact potential secret keys, passwords, bearer tokens
        return arg.replace(/(bearer\s+[a-zA-Z0-9_\-\.]+)/gi, 'Bearer [REDACTED]')
                  .replace(/(password=["']?)([^"'\s&]+)(["']?)/gi, '$1[REDACTED]$3');
      }
      return arg;
    });
  }
}

export const createScopedLogger = (source: LogSource, env?: ExtensionEnvironment): Logger => {
  return new Logger(source, env);
};
