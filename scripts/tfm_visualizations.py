"""
TFM Visualizations - Render transition data as diagrams

Provides visualization functions for TransitionTracker data following SOLID principles:
- Single Responsibility: Only handles visualization rendering
- Open/Closed: Easy to add new diagram types without modifying tracker
- Dependency Inversion: Depends on tracker's public API, not internals
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tfm_decorator import TransitionTracker


def render_sankey(
    tracker: "TransitionTracker",
    include_failures: bool = True,
    min_transitions: int = 1,
) -> str:
    """
    Generate Mermaid Sankey diagram from transition data.
    
    Sankey diagrams visualize flow between states with link width proportional
    to transition volume. Shows where workflows succeed and where they fail.
    
    Args:
        tracker: TransitionTracker instance with recorded transitions
        include_failures: If True, failed transitions flow to "FAIL" node
        min_transitions: Minimum transitions to include (filters noise)
        
    Returns:
        Mermaid markdown string ready to render
        
    Example:
        ```python
        tracker = TransitionTracker.get_instance()
        # ... run workflows ...
        sankey = render_sankey(tracker)
        print(sankey)  # Copy to markdown file
        ```
    """
    rates = tracker.get_transition_rates()
    
    if not rates:
        return "```mermaid\nsankey-beta\n\nNo transitions recorded\n```"
    
    lines = [
        "```mermaid",
        "---",
        "config:",
        "  sankey:",
        "    showValues: true",
        "---",
        "sankey-beta",
        "",
    ]
    
    # Track which states have outgoing transitions
    states_with_outflow = set()
    
    # Generate success flows: source,target,successes
    for transition, stats in sorted(rates.items()):
        parts = transition.split(" → ")
        if len(parts) != 2:
            continue
            
        from_state, to_state = parts
        successes = stats["successes"]
        failures = stats["failures"]
        
        # Filter by minimum threshold
        if successes < min_transitions and failures < min_transitions:
            continue
        
        # Add successful transitions
        if successes >= min_transitions:
            lines.append(f"{from_state},{to_state},{successes}")
            states_with_outflow.add(from_state)
        
        # Add failed transitions to FAIL node
        if include_failures and failures >= min_transitions:
            lines.append(f"{from_state},FAIL,{failures}")
            states_with_outflow.add(from_state)
    
    lines.append("```")
    return "\n".join(lines)


def render_sankey_success_only(
    tracker: "TransitionTracker",
    min_transitions: int = 1,
) -> str:
    """
    Generate Sankey diagram showing only successful transitions.
    
    Useful for visualizing the "happy path" through your workflow.
    
    Args:
        tracker: TransitionTracker instance
        min_transitions: Minimum transitions to include
        
    Returns:
        Mermaid markdown string
    """
    return render_sankey(tracker, include_failures=False, min_transitions=min_transitions)


# Example usage
if __name__ == "__main__":
    from collections import defaultdict
    
    # Mock tracker for demonstration
    class MockTracker:
        def get_transition_rates(self):
            return {
                "START → ParseRequest": {
                    "total": 20,
                    "failures": 0,
                    "successes": 20,
                    "failure_rate": 0.0,
                    "avg_duration_ms": 5.0,
                },
                "ParseRequest → ClassifyIntent": {
                    "total": 20,
                    "failures": 4,
                    "successes": 16,
                    "failure_rate": 20.0,
                    "avg_duration_ms": 10.0,
                },
                "ClassifyIntent → ExecuteQuery": {
                    "total": 16,
                    "failures": 9,
                    "successes": 7,
                    "failure_rate": 56.2,
                    "avg_duration_ms": 50.0,
                },
                "ExecuteQuery → FormatResponse": {
                    "total": 7,
                    "failures": 0,
                    "successes": 7,
                    "failure_rate": 0.0,
                    "avg_duration_ms": 15.0,
                },
                "FormatResponse → END": {
                    "total": 7,
                    "failures": 0,
                    "successes": 7,
                    "failure_rate": 0.0,
                    "avg_duration_ms": 2.0,
                },
            }
    
    tracker = MockTracker()
    
    print("=" * 70)
    print("SANKEY DIAGRAM - WITH FAILURES")
    print("=" * 70)
    print()
    print(render_sankey(tracker, include_failures=True))
    print()
    
    print("=" * 70)
    print("SANKEY DIAGRAM - SUCCESS PATH ONLY")
    print("=" * 70)
    print()
    print(render_sankey_success_only(tracker))
    print()
    
    print("=" * 70)
    print("Copy the above into a markdown file or GitHub to render")
    print("=" * 70)
