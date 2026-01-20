/**
 * Transition Failure Matrix (TFM) Logger
 * Tracks state transitions in the LLM Council workflow for failure analysis.
 */

import { DebateFramework } from '../constants';

export interface TransitionEvent {
  fromState: string;
  toState: string;
  status: 'SUCCESS' | 'FAILURE';
  error?: string;
  timestamp: number;
  framework: DebateFramework;
  agentRole?: string;
  modelId?: string;
  metadata?: Record<string, unknown>;
}

const STORAGE_KEY = 'tfm_transitions';
const MAX_STORED_TRANSITIONS = 1000; // Prevent localStorage overflow

/**
 * Log a state transition event.
 * Events are stored in localStorage for later analysis.
 */
export function logTransition(event: TransitionEvent): void {
  const statusSymbol = event.status === 'SUCCESS' ? '✓' : '✗';
  const logMsg = `TFM: ${event.fromState} -> ${event.toState} ${statusSymbol}`;

  if (event.status === 'FAILURE') {
    console.error(logMsg, event.error ? `| ERROR: ${event.error}` : '');
  } else {
    console.log(logMsg);
  }

  // Store for later analysis
  try {
    const transitions = getStoredTransitions();
    transitions.push(event);

    // Keep only the most recent transitions to prevent overflow
    if (transitions.length > MAX_STORED_TRANSITIONS) {
      transitions.splice(0, transitions.length - MAX_STORED_TRANSITIONS);
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(transitions));
  } catch (e) {
    // Silently fail if localStorage is unavailable/full
    console.warn('TFM: Could not store transition:', e);
  }
}

/**
 * Retrieve all stored transition events.
 */
export function getStoredTransitions(): TransitionEvent[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

/**
 * Clear all stored transition events.
 */
export function clearTransitions(): void {
  localStorage.removeItem(STORAGE_KEY);
}

/**
 * Get transition count by status.
 */
export function getTransitionStats(): { total: number; successes: number; failures: number } {
  const transitions = getStoredTransitions();
  return {
    total: transitions.length,
    successes: transitions.filter(t => t.status === 'SUCCESS').length,
    failures: transitions.filter(t => t.status === 'FAILURE').length
  };
}
