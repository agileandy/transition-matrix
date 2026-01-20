"""
Transition Failure Matrix - Decorator Instrumentation

Provides decorators for automatic transition tracking in Python workflows.

Usage:
    from tfm_decorator import TransitionTracker, track_state

    tracker = TransitionTracker()

    @track_state("ParseRequest")
    async def parse_request(data):
        ...

    @track_state("ClassifyIntent")
    async def classify_intent(parsed):
        ...

    # After running, get the matrix
    print(tracker.get_hotspots())
"""

import asyncio
import functools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class TransitionEvent:
    """Record of a single transition."""

    from_state: str
    to_state: str
    success: bool
    timestamp: datetime
    duration_ms: float
    error_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class TransitionTracker:
    """
    Tracks state transitions and builds failure matrix.

    Thread-safe for concurrent workflows using workflow_id isolation.
    """

    _instance: Optional["TransitionTracker"] = None

    def __init__(self):
        self.events: list[TransitionEvent] = []
        self.current_state: dict[str, str] = {}  # workflow_id -> state
        self.matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    @classmethod
    def get_instance(cls) -> "TransitionTracker":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None

    def set_state(self, state: str, workflow_id: str = "default"):
        """Explicitly set current state for a workflow."""
        self.current_state[workflow_id] = state

    def get_current_state(self, workflow_id: str = "default") -> Optional[str]:
        """Get current state for a workflow."""
        return self.current_state.get(workflow_id)

    def record_transition(
        self,
        from_state: str,
        to_state: str,
        success: bool,
        duration_ms: float = 0,
        error_message: Optional[str] = None,
        workflow_id: str = "default",
        **metadata: Any,
    ):
        """Record a transition event."""
        event = TransitionEvent(
            from_state=from_state,
            to_state=to_state,
            success=success,
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            error_message=error_message,
            metadata=metadata,
        )
        self.events.append(event)

        if not success:
            self.matrix[from_state][to_state] += 1

        # Log for external consumption (matches expected log format)
        status = "SUCCESS" if success else "FAILURE"
        log_msg = f"TRANSITION: {from_state} -> {to_state} {status}"
        if error_message:
            log_msg += f" ERROR: {error_message}"

        logger.info(
            log_msg,
            extra={
                "from_state": from_state,
                "to_state": to_state,
                "success": success,
                "duration_ms": duration_ms,
                "workflow_id": workflow_id,
            },
        )

        # Update current state if successful
        if success:
            self.current_state[workflow_id] = to_state

    def get_matrix_summary(self) -> dict:
        """Get current matrix state."""
        states: set[str] = set()
        for from_s in self.matrix:
            states.add(from_s)
            for to_s in self.matrix[from_s]:
                states.add(to_s)

        # Also include states from events (for success-only states)
        for event in self.events:
            states.add(event.from_state)
            states.add(event.to_state)

        return {
            "states": sorted(states),
            "matrix": {k: dict(v) for k, v in self.matrix.items()},
            "total_events": len(self.events),
            "total_failures": sum(1 for e in self.events if not e.success),
        }

    def get_hotspots(self, min_count: int = 1) -> list[tuple[str, str, int]]:
        """Return failure hotspots sorted by count."""
        hotspots = []
        for from_state, to_states in self.matrix.items():
            for to_state, count in to_states.items():
                if count >= min_count:
                    hotspots.append((from_state, to_state, count))
        return sorted(hotspots, key=lambda x: -x[2])

    def reset(self):
        """Clear all tracking data."""
        self.events.clear()
        self.current_state.clear()
        self.matrix.clear()

    def render_markdown(self) -> str:
        """Render the current matrix as Markdown."""
        summary = self.get_matrix_summary()
        states = summary["states"]

        if not states:
            return "# Transition Failure Matrix\n\nNo transitions recorded."

        lines = ["# Transition Failure Matrix\n"]
        lines.append(f"**Total Events:** {summary['total_events']}")
        lines.append(f"**Total Failures:** {summary['total_failures']}\n")

        # Header
        header = "| From \\ To |"
        separator = "|-----------|"
        for state in states:
            header += f" {state} |"
            separator += "--------|"
        lines.append(header)
        lines.append(separator)

        # Rows
        for from_state in states:
            row = f"| **{from_state}** |"
            for to_state in states:
                count = self.matrix[from_state][to_state]
                if count > 0:
                    row += f" **{count}** |"
                else:
                    row += " - |"
            lines.append(row)

        # Hotspots
        hotspots = self.get_hotspots(min_count=2)
        if hotspots:
            lines.append("\n## Hotspots\n")
            for from_s, to_s, count in hotspots[:10]:
                lines.append(f"- {from_s} -> {to_s}: **{count} failures**")

        return "\n".join(lines)


def track_state(
    state_name: str,
    tracker: Optional[TransitionTracker] = None,
    workflow_id: str = "default",
):
    """
    Decorator to track state transitions.

    Automatically records transition from previous state to this state,
    and captures success/failure based on whether function completes.

    Usage:
        @track_state("ParseRequest")
        def parse_request(data):
            return parsed_data

        @track_state("ClassifyIntent")
        async def classify_intent(parsed):
            return classification
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            _tracker = tracker or TransitionTracker.get_instance()
            from_state = _tracker.get_current_state(workflow_id) or "START"

            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                _tracker.record_transition(
                    from_state=from_state,
                    to_state=state_name,
                    success=True,
                    duration_ms=duration_ms,
                    workflow_id=workflow_id,
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                _tracker.record_transition(
                    from_state=from_state,
                    to_state=state_name,
                    success=False,
                    duration_ms=duration_ms,
                    error_message=str(e),
                    workflow_id=workflow_id,
                )
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            _tracker = tracker or TransitionTracker.get_instance()
            from_state = _tracker.get_current_state(workflow_id) or "START"

            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                _tracker.record_transition(
                    from_state=from_state,
                    to_state=state_name,
                    success=True,
                    duration_ms=duration_ms,
                    workflow_id=workflow_id,
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                _tracker.record_transition(
                    from_state=from_state,
                    to_state=state_name,
                    success=False,
                    duration_ms=duration_ms,
                    error_message=str(e),
                    workflow_id=workflow_id,
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_transition(from_state: str, to_state: str):
    """
    Decorator for explicit transition tracking.

    Use when you know both the source and target states explicitly.

    Usage:
        @track_transition("DecideTool", "ExecSQL")
        def execute_sql(query):
            return db.execute(query)
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracker = TransitionTracker.get_instance()
            start_time = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                tracker.record_transition(
                    from_state=from_state,
                    to_state=to_state,
                    success=True,
                    duration_ms=duration_ms,
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                tracker.record_transition(
                    from_state=from_state,
                    to_state=to_state,
                    success=False,
                    duration_ms=duration_ms,
                    error_message=str(e),
                )
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracker = TransitionTracker.get_instance()
            start_time = time.perf_counter()

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                tracker.record_transition(
                    from_state=from_state,
                    to_state=to_state,
                    success=True,
                    duration_ms=duration_ms,
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                tracker.record_transition(
                    from_state=from_state,
                    to_state=to_state,
                    success=False,
                    duration_ms=duration_ms,
                    error_message=str(e),
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Example usage and self-test
if __name__ == "__main__":
    import random

    # Configure logging to see transitions
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )

    # Reset for clean test
    TransitionTracker.reset_instance()
    tracker = TransitionTracker.get_instance()

    @track_state("ParseRequest")
    def parse_request(data: str) -> dict:
        if not data:
            raise ValueError("Empty request")
        return {"parsed": data}

    @track_state("ClassifyIntent")
    def classify_intent(parsed: dict) -> str:
        if random.random() < 0.3:
            raise RuntimeError("Classification failed")
        return "query"

    @track_state("ExecuteQuery")
    def execute_query(intent: str) -> str:
        if random.random() < 0.4:
            raise RuntimeError("Query execution failed")
        return "result"

    # Simulate workflow runs
    print("\n=== Running simulated workflow ===\n")
    for i in range(20):
        tracker.set_state("START")  # Reset for each run
        try:
            parsed = parse_request(f"request_{i}")
            intent = classify_intent(parsed)
            result = execute_query(intent)
            print(f"Run {i}: SUCCESS")
        except Exception as e:
            print(f"Run {i}: FAILED - {e}")

    # Print results
    print("\n=== Transition Failure Matrix ===\n")
    print(tracker.render_markdown())

    print("\n=== Hotspots ===\n")
    for from_s, to_s, count in tracker.get_hotspots():
        print(f"  {from_s} -> {to_s}: {count} failures")
