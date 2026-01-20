# Sample Transition Failure Matrix

This example shows a complete analysis workflow for an LLM agent pipeline.

## Scenario

An LLM-based SQL query agent has the following workflow:

```
User Request → ParseReq → IntentClass → DecideTool → GenSQL → ExecSQL → FormatResp
                                              ↓
                                           PlanCal → ExecCal
```

The agent handles both SQL queries and calendar operations.

---

## Sample Log Data

```
2025-01-20T10:00:01 TRANSITION: START -> ParseReq SUCCESS
2025-01-20T10:00:02 TRANSITION: ParseReq -> IntentClass SUCCESS
2025-01-20T10:00:03 TRANSITION: IntentClass -> DecideTool SUCCESS
2025-01-20T10:00:04 TRANSITION: DecideTool -> GenSQL SUCCESS
2025-01-20T10:00:05 TRANSITION: GenSQL -> ExecSQL FAILURE ERROR: Invalid SQL syntax
2025-01-20T10:00:06 TRANSITION: START -> ParseReq SUCCESS
2025-01-20T10:00:07 TRANSITION: ParseReq -> IntentClass SUCCESS
2025-01-20T10:00:08 TRANSITION: IntentClass -> DecideTool SUCCESS
2025-01-20T10:00:09 TRANSITION: DecideTool -> GenSQL SUCCESS
2025-01-20T10:00:10 TRANSITION: GenSQL -> ExecSQL FAILURE ERROR: Permission denied
... (hundreds more transitions)
```

---

## Generated Matrix

After running `python tfm_analyze.py --log-file agent.log`:

# Transition Failure Matrix

**Total Transitions:** 847
**Total Failures:** 45
**Failure Rate:** 5.3%

| From \ To | ParseReq | IntentClass | DecideTool | GenSQL | ExecSQL | PlanCal | ExecCal | FormatResp |
|-----------|----------|-------------|------------|--------|---------|---------|---------|------------|
| **START** | **2** | - | - | - | - | - | - | - |
| **ParseReq** | - | **3** | - | - | - | - | - | - |
| **IntentClass** | - | - | **4** | - | - | - | - | - |
| **DecideTool** | - | - | - | **6** | - | **2** | - | - |
| **GenSQL** | - | - | - | - | **12** | - | - | - |
| **ExecSQL** | - | - | - | - | **5** | - | - | - |
| **PlanCal** | - | - | - | - | - | - | **8** | - |
| **ExecCal** | - | - | - | - | - | - | **3** | - |

## Hotspots (failures >= 2)

- GenSQL -> ExecSQL: **12 failures**
- PlanCal -> ExecCal: **8 failures**
- DecideTool -> GenSQL: **6 failures**
- ExecSQL -> ExecSQL: **5 failures** (retry loop)
- IntentClass -> DecideTool: **4 failures**
- ExecCal -> ExecCal: **3 failures** (retry loop)
- ParseReq -> IntentClass: **3 failures**
- START -> ParseReq: **2 failures**
- DecideTool -> PlanCal: **2 failures**

---

## Interpretation

### Primary Hotspot: GenSQL → ExecSQL (12 failures)

**What it means:** SQL generation succeeds, but execution fails.

**Likely causes:**
- LLM generates syntactically valid but semantically incorrect SQL
- Permission issues on certain tables
- Query timeouts on large datasets
- Connection pool exhaustion

**Investigation steps:**
1. Sample error messages from this transition
2. Check if specific table names correlate with failures
3. Review SQL validation before execution
4. Analyze query complexity and timeout settings

**Recommended action:**
- Add SQL validation layer between GenSQL and ExecSQL
- Implement query cost estimation
- Add retry with exponential backoff for transient errors

---

### Secondary Hotspot: PlanCal → ExecCal (8 failures)

**What it means:** Calendar planning works, but execution fails.

**Likely causes:**
- API rate limiting
- Authentication token expiry
- Calendar conflicts

**Recommended action:**
- Implement rate limit handling with backoff
- Add token refresh before calendar operations
- Pre-check for conflicts before attempting booking

---

### Retry Loop: ExecSQL → ExecSQL (5 failures)

**What it means:** SQL execution is retrying without fixing the root cause.

**Likely causes:**
- Retry logic without error classification
- Transient errors being treated as retryable
- Missing circuit breaker

**Recommended action:**
- Classify errors as retryable vs. permanent
- Add circuit breaker to prevent infinite retries
- Log distinct error types for each retry

---

## Actions Taken

Based on this analysis, the following bugs were created:

### Bug #1: High failure rate GenSQL → ExecSQL

```
Title: Add SQL validation layer between generation and execution
Priority: High
Tags: transition-failure, GenSQL, ExecSQL

Description:
- 12 failures at GenSQL → ExecSQL transition
- Need SQL syntax validation before execution
- Should catch common LLM generation errors
```

### Bug #2: Calendar API rate limiting

```
Title: Implement rate limit handling for calendar operations
Priority: Medium
Tags: transition-failure, PlanCal, ExecCal

Description:
- 8 failures at PlanCal → ExecCal transition
- Implement exponential backoff on rate limit responses
- Add proactive rate tracking
```

### Bug #3: Retry loop without circuit breaker

```
Title: Add circuit breaker to SQL execution retry logic
Priority: High
Tags: transition-failure, ExecSQL, retry-loop

Description:
- 5 self-referential failures (ExecSQL → ExecSQL)
- Indicates retry without progress
- Need circuit breaker to fail fast
```

---

## Follow-up Matrix (After Fixes)

After implementing fixes and deploying:

| From \ To | ... | GenSQL | ExecSQL | ... |
|-----------|-----|--------|---------|-----|
| **GenSQL** | ... | - | **2** | ... |

GenSQL → ExecSQL reduced from 12 to 2 failures (83% improvement).

---

## Key Learnings

1. **Hotspots reveal architectural gaps** - The GenSQL → ExecSQL hotspot revealed a missing validation layer.

2. **Diagonal entries signal retry issues** - Self-referential failures (A → A) indicate retry loops that need circuit breakers.

3. **Row analysis shows unstable states** - If a row has many failures, that state is likely unstable.

4. **Track improvement over time** - Save matrices to measure the impact of fixes.
