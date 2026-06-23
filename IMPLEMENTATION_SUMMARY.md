# NDJSON Streaming Implementation Summary

## Overview
Successfully implemented **Newline-Delimited JSON (NDJSON) streaming** for the `kuberef` tool when combining `--watch` and `--json` flags. This resolves issue #53.

## What Was Done

### 1. Created `ndjson_streaming.py` Module
- **Purpose**: Core NDJSON event streaming logic
- **Key Class**: `NDJSONEventStream`
- **Features**:
  - Conditional streaming based on flag combination
  - Single-line JSON output (no indentation)
  - UTC timestamp generation for all events
  - Event types: `watcher_started`, `change_detected`, `audit_summary`, `watcher_stopped`
  - Immediate output flushing for real-time streaming

### 2. Updated `main.py`
- Integrated `NDJSONEventStream` initialization
- Added conditional output suppression:
  - Suppresses human-readable logs when both `--watch` and `--json` are active
  - Preserves existing behavior for other flag combinations
- Emits lifecycle events:
  - `watcher_started` when watch mode begins
  - `audit_summary` after each audit (flattened to single line)
  - `watcher_stopped` when watch mode exits
- Updated docstring with NDJSON usage example

### 3. Updated `watcher.py`
- Enhanced `YamlAuditHandler` to accept stream parameter
- Emits `change_detected` events when files change
- Distinguishes between `modified` and `created` events
- Suppresses human-readable console output when NDJSON streaming is enabled
- Maintains cooldown behavior across streaming modes

### 4. Added Comprehensive Tests (`test_ndjson_streaming.py`)
- **NDJSON Format Tests**:
  - Verifies single-line JSON output
  - Confirms jq compatibility
  - Tests each event type
- **Integration Tests**:
  - Handler behavior with/without streaming
  - Cooldown mechanism in NDJSON mode
  - Watch mode message suppression
- **29 test cases** covering all scenarios

### 5. Created Documentation (`docs/NDJSON_STREAMING.md`)
- Complete usage guide
- Event type specifications with examples
- Integration examples with jq and data pipelines
- Troubleshooting section
- Backward compatibility notes

## Event Schema

### All Events Include
```json
{
  "event": "<event_type>",
  "timestamp": "<ISO-8601 UTC>"
}
```

### Event Types

**1. watcher_started**
```json
{"event":"watcher_started","timestamp":"...","watch_path":"/path"}
```

**2. change_detected**
```json
{"event":"change_detected","timestamp":"...","file_path":"/path/file.yaml","change_type":"modified|created"}
```

**3. audit_summary**
```json
{"event":"audit_summary","timestamp":"...","files_scanned":N,"passes":N,"failures":N,"warnings":N,"files":[...]}
```

**4. watcher_stopped**
```json
{"event":"watcher_stopped","timestamp":"..."}
```

## Usage Examples

### Basic NDJSON Streaming
```bash
poetry run kuberef ./test-manifests/ --watch --json
```

### Filter with jq
```bash
poetry run kuberef ./test-manifests/ --watch --json | jq --unbuffered 'select(.event == "audit_summary")'
```

### Extract Specific Fields
```bash
poetry run kuberef ./test-manifests/ --watch --json | jq '.timestamp, .failures'
```

## Files Modified/Created

```
✅ src/kuberef/ndjson_streaming.py       (NEW - 60 lines)
✅ src/kuberef/main.py                   (MODIFIED - Added NDJSON integration)
✅ src/kuberef/watcher.py                (MODIFIED - Added event emission)
✅ tests/test_ndjson_streaming.py        (NEW - 290+ lines, 29 test cases)
✅ docs/NDJSON_STREAMING.md              (NEW - Comprehensive documentation)
```

## Key Features

✅ **Suppresses human-readable output** when `--watch` AND `--json` are active
✅ **Single-line JSON** - No indentation, perfect for streaming
✅ **Event discrimination** - Each event has a clear `event` field
✅ **UTC timestamps** - ISO 8601 format on all events
✅ **jq compatible** - Can pipe directly to jq with `--unbuffered`
✅ **Backward compatible** - Existing behavior unchanged for other flag combinations
✅ **Well-tested** - 29 test cases covering all scenarios
✅ **Documented** - Complete usage guide and examples

## Backward Compatibility

| Flags | Behavior |
|-------|----------|
| `--json` only | Pretty-printed JSON (existing behavior) |
| `--watch` only | Human-readable output (existing behavior) |
| `--watch --json` | NDJSON streaming (NEW) |
| No flags | Human-readable output (existing behavior) |

## Testing

Run all NDJSON tests:
```bash
pytest tests/test_ndjson_streaming.py -v
```

Run specific test:
```bash
pytest tests/test_ndjson_streaming.py::TestNDJSONEventStream::test_ndjson_stream_parseable_by_jq -v
```

## Verification Command (from Issue #53)

```bash
poetry run kuberef ./test-manifests/ --watch --json | jq --unbuffered 'select(.event == "audit_summary")'
```

This command will now:
1. ✅ Output only audit_summary events
2. ✅ Parse successfully with jq (no syntax errors)
3. ✅ Work with stream processing tools

## Commits

1. `feat: Add NDJSON event streaming utility module` - Created ndjson_streaming.py
2. `feat: Integrate NDJSON streaming into main.py with conditional output` - Updated main.py
3. `feat: Update watcher.py to emit NDJSON change_detected events` - Updated watcher.py
4. `test: Add comprehensive unit tests for NDJSON streaming` - Added tests
5. `docs: Add comprehensive NDJSON streaming documentation` - Added documentation

## Next Steps

1. Create Pull Request to `hudazaan/kuberef` main branch
2. Request review from maintainers
3. Address any feedback
4. Merge once approved
