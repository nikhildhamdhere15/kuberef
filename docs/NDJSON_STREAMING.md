# NDJSON Streaming Feature Documentation

## Overview

This document describes the **Newline-Delimited JSON (NDJSON) streaming** feature implemented for the `kuberef` tool when combining `--watch` and `--json` flags.

## What is NDJSON?

NDJSON (also known as JSON Lines or JSONL) is a format where each line is a valid JSON object. This format is ideal for:
- **Streaming data**: Each line can be processed independently
- **Piping to tools like `jq`**: Line-by-line processing without buffering issues
- **Data lake ingestion**: Systems that expect line-delimited JSON

## Usage

### Basic Command

```bash
poetry run kuberef ./test-manifests/ --watch --json
```

When both `--watch` and `--json` flags are active:
1. All human-readable logs are suppressed
2. All events are emitted as single-line JSON objects
3. Each line can be filtered and processed independently

### Piping with jq

Filter only audit summary events:
```bash
poetry run kuberef ./test-manifests/ --watch --json | jq 'select(.event == "audit_summary")'
```

Filter change detection events:
```bash
poetry run kuberef ./test-manifests/ --watch --json | jq 'select(.event == "change_detected")'
```

Get all events with specific field:
```bash
poetry run kuberef ./test-manifests/ --watch --json | jq '.timestamp'
```

## Event Types

### 1. `watcher_started`

Emitted when watch mode begins.

**Example:**
```json
{"event":"watcher_started","timestamp":"2026-06-23T11:15:30.123456","watch_path":"/home/user/manifests"}
```

**Fields:**
- `event`: `"watcher_started"`
- `timestamp`: ISO 8601 UTC timestamp
- `watch_path`: Directory or file being watched

---

### 2. `change_detected`

Emitted when a YAML file is modified or created.

**Example (modified):**
```json
{"event":"change_detected","timestamp":"2026-06-23T11:15:45.654321","file_path":"/home/user/manifests/deployment.yaml","change_type":"modified"}
```

**Example (created):**
```json
{"event":"change_detected","timestamp":"2026-06-23T11:15:50.111111","file_path":"/home/user/manifests/new-service.yaml","change_type":"created"}
```

**Fields:**
- `event`: `"change_detected"`
- `timestamp`: ISO 8601 UTC timestamp
- `file_path`: Path to the changed file
- `change_type`: Either `"modified"` or `"created"`

---

### 3. `audit_summary`

Emitted after audit completes (on startup and after each file change).

**Example:**
```json
{"event":"audit_summary","timestamp":"2026-06-23T11:15:46.987654","files_scanned":3,"passes":9,"failures":1,"warnings":2,"files":[{"file":"deployment.yaml","results":[{"secret":"app-secret","status":"PASS"},{"secret":"db-secret","status":"FAIL"}]},{"file":"service.yaml","results":[{"secret":"tls-secret","status":"WARNING","missing_keys":["cert.pem"]}]}]}
```

**Fields:**
- `event`: `"audit_summary"`
- `timestamp`: ISO 8601 UTC timestamp
- `files_scanned`: Number of YAML files audited
- `passes`: Count of passed secret validations
- `failures`: Count of failed secret validations (secret not found)
- `warnings`: Count of warning validations (secret found but keys missing)
- `files`: Array of audit results per file
  - `file`: Filename
  - `results`: Array of validation results
    - `secret`: Secret name
    - `status`: One of `"PASS"`, `"FAIL"`, `"WARNING"`
    - `missing_keys`: (only in warnings) Array of missing secret keys

---

### 4. `watcher_stopped`

Emitted when watch mode exits (on Ctrl+C).

**Example:**
```json
{"event":"watcher_stopped","timestamp":"2026-06-23T11:20:00.555555"}
```

**Fields:**
- `event`: `"watcher_stopped"`
- `timestamp`: ISO 8601 UTC timestamp

---

## Format Guarantees

✅ **Single-line JSON**: No indentation or multi-line formatting
✅ **Line-delimited**: Each event ends with `\n` (newline)
✅ **Valid JSON**: Each line is independently parseable JSON
✅ **jq compatible**: Can be piped directly to `jq` with `--unbuffered` flag
✅ **UTC timestamps**: All timestamps are in ISO 8601 format (UTC)

## Example: Complete Stream Session

```bash
$ poetry run kuberef ./manifests/ --watch --json
{"event":"watcher_started","timestamp":"2026-06-23T11:30:00.000000","watch_path":"./manifests"}
{"event":"audit_summary","timestamp":"2026-06-23T11:30:01.111111","files_scanned":2,"passes":5,"failures":0,"warnings":0,"files":[...]}
{"event":"change_detected","timestamp":"2026-06-23T11:30:15.222222","file_path":"./manifests/deployment.yaml","change_type":"modified"}
{"event":"audit_summary","timestamp":"2026-06-23T11:30:16.333333","files_scanned":2,"passes":5,"failures":0,"warnings":0,"files":[...]}
{"event":"watcher_stopped","timestamp":"2026-06-23T11:30:20.444444"}
```

## Integration with Data Pipelines

### Filter by event type
```bash
poetry run kuberef ./manifests/ --watch --json | jq 'select(.event == "audit_summary")' | jq '.files_scanned'
```

### Extract failures only
```bash
poetry run kuberef ./manifests/ --watch --json | jq 'select(.event == "audit_summary" and .failures > 0)'
```

### Stream to log aggregation
```bash
poetry run kuberef ./manifests/ --watch --json | jq -c '.event, .timestamp, .failures' | tee kuberef-audit.log
```

### Send to metrics system
```bash
poetry run kuberef ./manifests/ --watch --json | jq -c '{event: .event, timestamp: .timestamp, passed: .passes, failed: .failures}' | nc metrics-server 5000
```

## Backward Compatibility

- When `--watch` is used **without** `--json`: Human-readable output continues as before
- When `--json` is used **without** `--watch`: Pretty-printed JSON continues as before
- When **both** flags are used: NDJSON streaming is enabled

## Testing

Run the NDJSON streaming tests:
```bash
pytest tests/test_ndjson_streaming.py -v
```

Run all tests:
```bash
pytest tests/ -v
```

## Implementation Details

### Key Components

1. **`ndjson_streaming.py`**: Core NDJSON event emission logic
   - `NDJSONEventStream` class manages event streaming
   - Methods for each event type
   - Conditional output based on enabled flag

2. **`main.py`**: Integration of NDJSON with audit logic
   - Initializes stream based on flag combination
   - Suppresses human-readable output when streaming
   - Emits lifecycle events

3. **`watcher.py`**: File system event emission
   - Emits `change_detected` events
   - Suppresses console messages when streaming
   - Maintains existing cooldown behavior

4. **`test_ndjson_streaming.py`**: Comprehensive test suite
   - Tests stream enable/disable logic
   - Tests event format and parsability
   - Tests integration with watcher
   - Tests jq compatibility

## Troubleshooting

### jq not found
Install jq:
- **macOS**: `brew install jq`
- **Linux**: `sudo apt install jq`
- **Windows**: `winget install jqlang.jq` or `choco install jq`

### Output not appearing
Ensure you're using `--unbuffered` with jq:
```bash
poetry run kuberef ./manifests/ --watch --json | jq --unbuffered 'select(.event == "audit_summary")'
```

### Mixed human-readable and JSON output
This indicates the flags weren't recognized. Verify:
- You're using `--watch` AND `--json` together
- You're using the latest version of the code

## Future Enhancements

- Add optional fields for audit context (cluster name, namespace)
- Support custom event types for plugins
- Add event filtering at the CLI level
