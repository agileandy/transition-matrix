/**
 * Transition Failure Matrix (TFM) Analyzer
 * CLI utility for analyzing stored transition events and generating failure matrices.
 *
 * Usage in browser console:
 *   analyzeTransitions() - Display full analysis
 *   getTransitionMatrix() - Get raw matrix data
 *   clearTransitions() - Clear all stored transitions
 */

import { getStoredTransitions, clearTransitions, getTransitionStats } from '../services/transitionLogger';
import type { TransitionEvent } from '../services/transitionLogger';

export interface TransitionMatrix {
  matrix: Record<string, Record<string, { count: number; failures: number }>>;
  totalTransitions: number;
  totalFailures: number;
  failureRate: number;
  hotspots: Array<{
    from: string;
    to: string;
    count: number;
    failureRate: number;
    commonErrors: Array<{ error: string; count: number }>;
  }>;
}

/**
 * Generate a transition failure matrix from stored events.
 */
export function generateTransitionMatrix(): TransitionMatrix {
  const transitions = getStoredTransitions();

  // Build matrix
  const matrix: Record<string, Record<string, { count: number; failures: number }>> = {};
  const errorMap: Record<string, Record<string, Record<string, number>>> = {};

  for (const t of transitions) {
    const key = `${t.fromState}->${t.toState}`;

    if (!matrix[t.fromState]) {
      matrix[t.fromState] = {};
      errorMap[t.fromState] = {};
    }

    if (!matrix[t.fromState][t.toState]) {
      matrix[t.fromState][t.toState] = { count: 0, failures: 0 };
      errorMap[t.fromState][t.toState] = {};
    }

    matrix[t.fromState][t.toState].count++;

    if (t.status === 'FAILURE') {
      matrix[t.fromState][t.toState].failures++;

      // Track error messages
      if (t.error) {
        const errorKey = t.error.substring(0, 50); // Truncate long errors
        errorMap[t.fromState][t.toState][errorKey] = (errorMap[t.fromState][t.toState][errorKey] || 0) + 1;
      }
    }
  }

  // Calculate hotspots (transitions with 2+ failures, sorted by failure count)
  const hotspots: TransitionMatrix['hotspots'] = [];

  for (const [from, toStates] of Object.entries(matrix)) {
    for (const [to, stats] of Object.entries(toStates)) {
      if (stats.failures >= 2) {
        // Get common errors for this transition
        const errors = errorMap[from]?.[to] || {};
        const commonErrors = Object.entries(errors)
          .map(([error, count]) => ({ error, count }))
          .sort((a, b) => b.count - a.count)
          .slice(0, 3); // Top 3 errors

        hotspots.push({
          from,
          to,
          count: stats.failures,
          failureRate: stats.count > 0 ? stats.failures / stats.count : 0,
          commonErrors
        });
      }
    }
  }

  hotspots.sort((a, b) => b.count - a.count);

  const totalFailures = transitions.filter(t => t.status === 'FAILURE').length;

  return {
    matrix,
    totalTransitions: transitions.length,
    totalFailures,
    failureRate: transitions.length > 0 ? totalFailures / transitions.length : 0,
    hotspots
  };
}

/**
 * Display transition analysis in browser console.
 * Call this function from the browser DevTools console.
 */
export function analyzeTransitions(): void {
  const stats = getTransitionStats();
  const matrix = generateTransitionMatrix();

  console.log('\n=== TRANSITION FAILURE MATRIX ANALYSIS ===\n');

  // Summary
  console.log('SUMMARY:');
  console.log(`  Total Transitions: ${stats.total}`);
  console.log(`  Successes: ${stats.successes} (${((stats.successes / stats.total) * 100).toFixed(1)}%)`);
  console.log(`  Failures: ${stats.failures} (${((stats.failures / stats.total) * 100).toFixed(1)}%)`);
  console.log(`  Overall Failure Rate: ${(matrix.failureRate * 100).toFixed(1)}%`);

  // Hotspots
  if (matrix.hotspots.length > 0) {
    console.log('\n🔥 FAILURE HOTSPOTS (2+ failures):');
    console.table(matrix.hotspots.map(h => ({
      'From → To': `${h.from} -> ${h.to}`,
      'Failures': h.count,
      'Fail Rate': `${(h.failureRate * 100).toFixed(0)}%`,
      'Top Error': h.commonErrors[0]?.error || 'N/A'
    })));

    console.log('\nCommon errors by hotspot:');
    for (const hotspot of matrix.hotspots) {
      console.log(`  ${hotspot.from} -> ${hotspot.to}:`);
      for (const err of hotspot.commonErrors) {
        console.log(`    "${err.error}" (${err.count}x)`);
      }
    }
  } else {
    console.log('\n✅ No failure hotspots detected (all transitions < 2 failures)');
  }

  // Full matrix (optional - can be verbose)
  console.log('\n📊 FULL TRANSITION MATRIX:');
  const matrixFlat: Array<{ from: string; to: string; count: string }> = [];
  for (const [from, toStates] of Object.entries(matrix.matrix)) {
    for (const [to, stats] of Object.entries(toStates)) {
      matrixFlat.push({
        'From': from,
        'To': to,
        'Count': `${stats.count} (${stats.failures} failed)`
      });
    }
  }
  if (matrixFlat.length > 0) {
    console.table(matrixFlat);
  }

  console.log('\n=== END ANALYSIS ===\n');
}

/**
 * Export transitions as JSON for external analysis.
 */
export function exportTransitions(): string {
  const transitions = getStoredTransitions();
  return JSON.stringify(transitions, null, 2);
}

// Expose functions to window object for browser console access
declare global {
  interface Window {
    analyzeTransitions: typeof analyzeTransitions;
    getTransitionMatrix: typeof generateTransitionMatrix;
    exportTransitions: typeof exportTransitions;
    clearTransitions: typeof clearTransitions;
  }
}

// Auto-bind to window when module loads
if (typeof window !== 'undefined') {
  window.analyzeTransitions = analyzeTransitions;
  window.getTransitionMatrix = generateTransitionMatrix;
  window.exportTransitions = exportTransitions;
  window.clearTransitions = clearTransitions;
}

export default analyzeTransitions;
