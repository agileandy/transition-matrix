#!/usr/bin/env python3
"""
Transition Failure Matrix Analyzer

Parses log files to generate a transition failure matrix showing
where failures cluster in multi-step workflows.

Usage:
    python tfm_analyze.py --log-file agent.log --output matrix.md
    python tfm_analyze.py --states "State1,State2,State3" --format ascii
    cat logs.txt | python tfm_analyze.py --format json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional


class TransitionFailureMatrix:
    """Builds and renders a transition failure matrix."""

    def __init__(self, states: Optional[list[str]] = None):
        self.states = states or []
        self.matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.total_transitions = 0
        self.total_failures = 0
        self.discovered_states: set[str] = set()

    def record_failure(self, from_state: str, to_state: str):
        """Record a failure during a transition."""
        self.matrix[from_state][to_state] += 1
        self.total_failures += 1
        self.discovered_states.add(from_state)
        self.discovered_states.add(to_state)

    def record_transition(self, from_state: str, to_state: str, success: bool):
        """Record any transition (success or failure)."""
        self.total_transitions += 1
        self.discovered_states.add(from_state)
        self.discovered_states.add(to_state)
        if not success:
            self.record_failure(from_state, to_state)

    def get_all_states(self) -> list[str]:
        """Get all states in order."""
        if self.states:
            return self.states
        return sorted(self.discovered_states)

    def get_hotspots(self, min_count: int = 1) -> list[tuple[str, str, int]]:
        """Return failures sorted by count descending."""
        hotspots = []
        for from_state, to_states in self.matrix.items():
            for to_state, count in to_states.items():
                if count >= min_count:
                    hotspots.append((from_state, to_state, count))
        return sorted(hotspots, key=lambda x: -x[2])

    def render_markdown(self) -> str:
        """Render matrix as Markdown table."""
        states = self.get_all_states()
        if not states:
            return "# Transition Failure Matrix\n\nNo transitions found."

        lines = ["# Transition Failure Matrix\n"]
        failure_rate = (
            self.total_failures / self.total_transitions * 100
            if self.total_transitions > 0
            else 0
        )
        lines.append(f"**Total Transitions:** {self.total_transitions}")
        lines.append(f"**Total Failures:** {self.total_failures}")
        lines.append(f"**Failure Rate:** {failure_rate:.1f}%\n")

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

        # Hotspots summary
        hotspots = self.get_hotspots(min_count=2)
        if hotspots:
            lines.append("\n## Hotspots (failures >= 2)\n")
            for from_s, to_s, count in hotspots[:10]:
                lines.append(f"- {from_s} -> {to_s}: **{count} failures**")

        return "\n".join(lines)

    def render_ascii(self) -> str:
        """Render matrix as ASCII table."""
        states = self.get_all_states()
        if not states:
            return "No transitions found."

        # Calculate column widths
        max_state_len = max(len(s) for s in states)
        col_width = max(max_state_len, 4)

        lines = []
        lines.append(f"Total Transitions: {self.total_transitions}")
        lines.append(f"Total Failures: {self.total_failures}")
        lines.append("")

        # Header
        header = " " * (col_width + 3)
        for state in states:
            header += f"{state:^{col_width}} "
        lines.append(header)
        lines.append("-" * len(header))

        # Rows
        for from_state in states:
            row = f"{from_state:>{col_width}} |"
            for to_state in states:
                count = self.matrix[from_state][to_state]
                if count > 0:
                    row += f"{count:^{col_width}} "
                else:
                    row += f"{'·':^{col_width}} "
            lines.append(row)

        # Hotspots
        hotspots = self.get_hotspots(min_count=2)
        if hotspots:
            lines.append("")
            lines.append("Hotspots:")
            for from_s, to_s, count in hotspots[:5]:
                lines.append(f"  {from_s} -> {to_s}: {count}")

        return "\n".join(lines)

    def render_json(self, min_failures: int = 1) -> str:
        """Render matrix as JSON."""
        return json.dumps(
            {
                "states": self.get_all_states(),
                "matrix": {k: dict(v) for k, v in self.matrix.items()},
                "hotspots": [
                    {"from": f, "to": t, "count": c}
                    for f, t, c in self.get_hotspots(min_failures)
                ],
                "total_transitions": self.total_transitions,
                "total_failures": self.total_failures,
                "failure_rate": (
                    self.total_failures / self.total_transitions
                    if self.total_transitions > 0
                    else 0
                ),
            },
            indent=2,
        )


class LogParser:
    """Parse log files to extract transition data."""

    # Default patterns - can be customized
    TRANSITION_PATTERN = re.compile(
        r"TRANSITION:\s*(\w+)\s*->\s*(\w+)\s*(SUCCESS|FAILURE)", re.IGNORECASE
    )
    STATE_CHANGE_PATTERN = re.compile(r"STATE:\s*(\w+)")
    ERROR_PATTERN = re.compile(r"(ERROR|EXCEPTION|FAILED|FAILURE)", re.IGNORECASE)

    def __init__(self, states: Optional[list[str]] = None):
        self.states = states

    def parse_file(self, filepath: Path) -> TransitionFailureMatrix:
        """Parse a log file and return a failure matrix."""
        with open(filepath, encoding="utf-8", errors="replace") as f:
            return self.parse_lines(f.readlines())

    def parse_lines(self, lines: list[str]) -> TransitionFailureMatrix:
        """Parse log lines and build matrix."""
        matrix = TransitionFailureMatrix(self.states)

        # Track current state for implicit transitions
        current_state: Optional[str] = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for explicit transition logs
            match = self.TRANSITION_PATTERN.search(line)
            if match:
                from_state, to_state, result = match.groups()
                success = result.upper() == "SUCCESS"
                matrix.record_transition(from_state, to_state, success)
                current_state = to_state if success else from_state
                continue

            # Look for state change logs (implicit transitions)
            match = self.STATE_CHANGE_PATTERN.search(line)
            if match:
                new_state = match.group(1)
                if current_state and current_state != new_state:
                    # Check if this line also contains an error
                    is_error = bool(self.ERROR_PATTERN.search(line))
                    matrix.record_transition(current_state, new_state, not is_error)
                current_state = new_state

        return matrix


def main():
    parser = argparse.ArgumentParser(
        description="Transition Failure Matrix Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --log-file agent.log --output matrix.md
  %(prog)s --states "Parse,Route,Execute" --format ascii
  cat logs.txt | %(prog)s --format json
        """,
    )
    parser.add_argument(
        "--log-file",
        "-l",
        type=Path,
        help="Log file to analyze (reads stdin if not specified)",
    )
    parser.add_argument(
        "--states", "-s", help="Comma-separated list of states (auto-detected if omitted)"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "ascii", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--output", "-o", type=Path, help="Output file (stdout if not specified)"
    )
    parser.add_argument(
        "--min-failures",
        type=int,
        default=1,
        help="Minimum failures to show in hotspots (default: 1)",
    )

    args = parser.parse_args()

    # Parse states if provided
    states = args.states.split(",") if args.states else None
    log_parser = LogParser(states)

    # Parse log file or stdin
    if args.log_file:
        if not args.log_file.exists():
            print(f"Error: File not found: {args.log_file}", file=sys.stderr)
            sys.exit(1)
        matrix = log_parser.parse_file(args.log_file)
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("Reading from stdin (Ctrl+D to finish)...", file=sys.stderr)
        matrix = log_parser.parse_lines(sys.stdin.readlines())

    # Render output
    if args.format == "markdown":
        output = matrix.render_markdown()
    elif args.format == "ascii":
        output = matrix.render_ascii()
    else:  # json
        output = matrix.render_json(args.min_failures)

    # Write output
    if args.output:
        args.output.write_text(output)
        print(f"Matrix written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
