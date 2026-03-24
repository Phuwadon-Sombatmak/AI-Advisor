# Platform Validation Suite

Production-style validation runner for the AI investment platform.

## What it covers

- Data integrity
  - latest price parity
  - adjusted total return parity
  - technical indicator consistency
- Decision engine
  - 5-level recommendation consistency
  - conflict-rule validation
- AI responses
  - stock / sector / macro / Thai query structure
- Intent understanding
  - English and Thai intent routing
- Resilience
  - provider failure + cache fallback
  - full provider failure
- End-to-end API flow
  - prices -> stock -> recommendation -> AI advisor
  - optional Node login health check

## Run

From the project root:

```bash
npm run validate:platform
```

Or directly:

```bash
python3 qa/validation_runner.py
```

## Output

Results are written to:

- `qa/results/latest.json`
- `qa/results/history/<timestamp>.json`
- `qa/results/metrics.jsonl`

Each test emits:

```json
{
  "test_id": "DATA_PRICE_AAPL",
  "status": "PASS",
  "expected": "...",
  "actual": "...",
  "deviation": "...",
  "notes": "..."
}
```

## Optional live login check

Set these environment variables if you want the suite to validate the Node login route:

```bash
export QA_NODE_BASE_URL=http://localhost:5001
export QA_TEST_EMAIL=your-test-user@example.com
export QA_TEST_PASSWORD=your-test-password
```

Without these, the login flow check is recorded as an informational pass with a note.
