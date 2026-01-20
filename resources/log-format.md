# Transition Failure Matrix Log Format

This document specifies the log formats supported by the `tfm_analyze.py` CLI tool.

## Explicit Transition Logs (Recommended)

The most reliable format - explicitly logs each transition with its outcome.

### Format

```
TRANSITION: <from_state> -> <to_state> SUCCESS|FAILURE [ERROR: <message>]
```

### Examples

```
2025-01-20T10:15:30 TRANSITION: ParseReq -> IntentClass SUCCESS
2025-01-20T10:15:31 TRANSITION: IntentClass -> DecideTool SUCCESS
2025-01-20T10:15:32 TRANSITION: DecideTool -> GenSQL SUCCESS
2025-01-20T10:15:33 TRANSITION: GenSQL -> ExecSQL FAILURE ERROR: Connection timeout
2025-01-20T10:15:34 TRANSITION: GenSQL -> ExecSQL FAILURE ERROR: Invalid SQL syntax
2025-01-20T10:15:35 TRANSITION: GenSQL -> ExecSQL SUCCESS
2025-01-20T10:15:36 TRANSITION: ExecSQL -> FormatResp SUCCESS
```

### Python Implementation

```python
import logging

logger = logging.getLogger("transitions")

def log_transition(from_state: str, to_state: str, success: bool, error: str = None):
    """Log a state transition for failure matrix analysis."""
    status = "SUCCESS" if success else "FAILURE"
    msg = f"TRANSITION: {from_state} -> {to_state} {status}"
    if error:
        msg += f" ERROR: {error}"
    logger.info(msg)

# Usage
try:
    result = execute_sql(query)
    log_transition("GenSQL", "ExecSQL", success=True)
except Exception as e:
    log_transition("GenSQL", "ExecSQL", success=False, error=str(e))
    raise
```

---

## State Change Logs (Implicit Transitions)

Alternative format when you only log state changes. The tool infers transitions between consecutive states.

### Format

```
STATE: <state_name>
```

If an error keyword appears on the same line, the transition is marked as failure.

### Error Keywords

The tool looks for these patterns (case-insensitive):
- `ERROR`
- `EXCEPTION`
- `FAILED`
- `FAILURE`

### Examples

```
2025-01-20T10:15:30 STATE: ParseReq
2025-01-20T10:15:31 STATE: IntentClass
2025-01-20T10:15:32 STATE: DecideTool
2025-01-20T10:15:33 STATE: GenSQL
2025-01-20T10:15:34 STATE: ExecSQL ERROR: Database connection failed
2025-01-20T10:15:35 STATE: ExecSQL
2025-01-20T10:15:36 STATE: FormatResp
```

### Notes

- Less precise than explicit transition logs
- Error on line containing state change marks that transition as failed
- Tool tracks previous state to infer "from" state

---

## Structured JSON Logs

For systems using structured logging (e.g., JSON lines format).

### Format

```json
{
  "timestamp": "2025-01-20T10:15:32Z",
  "event": "transition",
  "from_state": "GenSQL",
  "to_state": "ExecSQL",
  "success": false,
  "error": "Database connection timeout",
  "duration_ms": 5023,
  "workflow_id": "req-12345"
}
```

### Notes

JSON format is not directly parsed by the CLI tool but can be converted:

```bash
# Convert JSON logs to explicit format
jq -r 'select(.event == "transition") |
  "TRANSITION: \(.from_state) -> \(.to_state) \(if .success then "SUCCESS" else "FAILURE" end)"' \
  logs.jsonl | python tfm_analyze.py
```

---

## Using the Decorator Library

The `tfm_decorator.py` module automatically generates logs in the explicit format:

```python
from tfm_decorator import track_state, TransitionTracker

@track_state("ParseRequest")
def parse_request(data):
    return parse(data)

@track_state("ClassifyIntent")
def classify_intent(parsed):
    return classify(parsed)
```

When these functions run, they emit logs like:

```
2025-01-20T10:15:30 TRANSITION: START -> ParseRequest SUCCESS
2025-01-20T10:15:31 TRANSITION: ParseRequest -> ClassifyIntent SUCCESS
```

Configure Python logging to capture these:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    handlers=[
        logging.FileHandler('agent.log'),
        logging.StreamHandler()
    ]
)
```

---

## Extracting Transitions from Existing Logs

If your logs don't match these formats exactly, use grep/ripgrep to extract and normalize:

```bash
# Extract lines containing state information
rg "entering state|state changed|executing" app.log > raw.log

# Manually normalize to expected format
# Or use sed/awk to transform
```

---

## Best Practices

1. **Use explicit format** - Most reliable, no inference needed
2. **Include timestamps** - Enables temporal analysis
3. **Include error messages** - Helps with root cause analysis
4. **Use consistent state names** - Avoid variations like "ParseReq" vs "ParseRequest"
5. **Log at INFO level** - Ensures visibility without noise
6. **Include workflow IDs** - Enables per-request analysis in concurrent systems
