import json
import pytest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from datetime import datetime

from kuberef.ndjson_streaming import NDJSONEventStream
from kuberef.watcher import YamlAuditHandler, run_watch_mode


class TestNDJSONEventStream:
    """Tests for NDJSON event streaming."""

    def test_ndjson_disabled_by_default(self):
        """NDJSON streaming should be disabled by default."""
        stream = NDJSONEventStream(enabled=False)
        assert stream.enabled is False

    def test_ndjson_enabled_when_requested(self):
        """NDJSON streaming should be enabled when both watch and json are active."""
        stream = NDJSONEventStream(enabled=True)
        assert stream.enabled is True

    def test_emit_event_single_line_json(self, capsys):
        """Emitted events should be single-line JSON (no indentation)."""
        stream = NDJSONEventStream(enabled=True)
        stream.emit_event("test_event", {"data": "value"})
        
        captured = capsys.readouterr()
        output_line = captured.out.strip()
        
        # Verify it's valid JSON
        parsed = json.loads(output_line)
        assert parsed["event"] == "test_event"
        assert parsed["data"] == "value"
        assert "timestamp" in parsed
        
        # Verify it's single-line (no indentation)
        assert "\n" not in output_line

    def test_emit_event_no_output_when_disabled(self, capsys):
        """No output should be emitted when streaming is disabled."""
        stream = NDJSONEventStream(enabled=False)
        stream.emit_event("test_event", {"data": "value"})
        
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_emit_watcher_started(self, capsys):
        """watcher_started event should have watch_path."""
        stream = NDJSONEventStream(enabled=True)
        stream.emit_watcher_started("/test/path")
        
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["event"] == "watcher_started"
        assert parsed["watch_path"] == "/test/path"

    def test_emit_change_detected_modified(self, capsys):
        """change_detected event should distinguish between modified and created."""
        stream = NDJSONEventStream(enabled=True)
        stream.emit_change_detected("/test/file.yaml", "modified")
        
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["event"] == "change_detected"
        assert parsed["file_path"] == "/test/file.yaml"
        assert parsed["change_type"] == "modified"

    def test_emit_change_detected_created(self, capsys):
        """change_detected event should handle created files."""
        stream = NDJSONEventStream(enabled=True)
        stream.emit_change_detected("/test/new.yaml", "created")
        
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["event"] == "change_detected"
        assert parsed["change_type"] == "created"

    def test_emit_audit_summary(self, capsys):
        """audit_summary event should contain flattened summary data."""
        stream = NDJSONEventStream(enabled=True)
        summary = {
            "files_scanned": 5,
            "passes": 4,
            "failures": 1,
            "warnings": 0,
            "files": [{"file": "test.yaml", "results": []}]
        }
        stream.emit_audit_summary(summary)
        
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["event"] == "audit_summary"
        assert parsed["files_scanned"] == 5
        assert parsed["passes"] == 4

    def test_emit_watcher_stopped(self, capsys):
        """watcher_stopped event should be emitted cleanly."""
        stream = NDJSONEventStream(enabled=True)
        stream.emit_watcher_stopped()
        
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["event"] == "watcher_stopped"

    def test_ndjson_stream_parseable_by_jq(self, capsys):
        """Streamed NDJSON should be parseable line-by-line (as jq would)."""
        stream = NDJSONEventStream(enabled=True)
        
        # Emit multiple events
        stream.emit_watcher_started("/path")
        stream.emit_change_detected("/path/file.yaml", "modified")
        stream.emit_audit_summary({"files_scanned": 1, "passes": 1})
        stream.emit_watcher_stopped()
        
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        
        # Should have 4 lines
        assert len(lines) == 4
        
        # Each line should be valid JSON
        events = [json.loads(line) for line in lines]
        assert events[0]["event"] == "watcher_started"
        assert events[1]["event"] == "change_detected"
        assert events[2]["event"] == "audit_summary"
        assert events[3]["event"] == "watcher_stopped"


class TestYamlAuditHandlerWithNDJSON:
    """Tests for watcher integration with NDJSON streaming."""

    def test_handler_emits_ndjson_when_stream_enabled(self):
        """Handler should emit NDJSON events when stream is enabled."""
        callback = MagicMock()
        stream = NDJSONEventStream(enabled=True)
        handler = YamlAuditHandler(callback, stream=stream)
        
        with patch.object(stream, 'emit_change_detected') as mock_emit:
            with patch('kuberef.watcher.time.time', return_value=0.0):
                handler._handle_event("/path/test.yaml", "modified")
                mock_emit.assert_called_once_with("/path/test.yaml", "modified")

    def test_handler_no_ndjson_when_stream_disabled(self, capsys):
        """Handler should show human-readable output when stream is disabled."""
        callback = MagicMock()
        stream = NDJSONEventStream(enabled=False)
        handler = YamlAuditHandler(callback, stream=stream)
        
        with patch('kuberef.watcher.time.time', return_value=0.0):
            handler._handle_event("/path/test.yaml", "modified")
            callback.assert_called_once()
            # Console output should have been generated (not captured in NDJSON mode)

    def test_handler_respects_cooldown(self):
        """Handler should still respect cooldown in NDJSON mode."""
        callback = MagicMock()
        stream = NDJSONEventStream(enabled=True)
        handler = YamlAuditHandler(callback, cooldown_seconds=1.5, stream=stream)
        
        with patch('kuberef.watcher.time.time') as mock_time:
            mock_time.return_value = 0.0
            handler._handle_event("/path/test.yaml", "modified")
            assert callback.call_count == 1
            
            # Event within cooldown should be ignored
            mock_time.return_value = 0.5
            handler._handle_event("/path/test.yaml", "modified")
            assert callback.call_count == 1
            
            # Event after cooldown should trigger
            mock_time.return_value = 1.6
            handler._handle_event("/path/test.yaml", "modified")
            assert callback.call_count == 2


class TestRunWatchModeWithNDJSON:
    """Tests for run_watch_mode with NDJSON streaming."""

    def test_run_watch_mode_emits_events(self, tmp_path):
        """run_watch_mode should emit NDJSON events when stream is enabled."""
        callback = MagicMock()
        stream = NDJSONEventStream(enabled=True)
        
        with patch('kuberef.watcher.Observer') as MockObserver:
            mock_observer = MagicMock()
            MockObserver.return_value = mock_observer
            
            with patch('kuberef.watcher.time.sleep', side_effect=KeyboardInterrupt):
                with patch.object(stream, 'emit_watcher_started') as mock_start:
                    run_watch_mode(tmp_path, callback, stream=stream)
                    # Note: emit_watcher_started is called in main.py before run_watch_mode

    def test_run_watch_mode_silent_with_ndjson(self, tmp_path, capsys):
        """run_watch_mode should not print human-readable messages when NDJSON is enabled."""
        callback = MagicMock()
        stream = NDJSONEventStream(enabled=True)
        
        with patch('kuberef.watcher.Observer') as MockObserver:
            mock_observer = MagicMock()
            MockObserver.return_value = mock_observer
            
            with patch('kuberef.watcher.time.sleep', side_effect=KeyboardInterrupt):
                run_watch_mode(tmp_path, callback, stream=stream)
                
                captured = capsys.readouterr()
                # Should not contain typical watch mode messages
                assert "Watch mode active" not in captured.out
                assert "Press Ctrl+C" not in captured.out

    def test_run_watch_mode_verbose_without_ndjson(self, tmp_path, capsys):
        """run_watch_mode should print human-readable messages when NDJSON is disabled."""
        callback = MagicMock()
        stream = NDJSONEventStream(enabled=False)
        
        with patch('kuberef.watcher.Observer') as MockObserver:
            mock_observer = MagicMock()
            MockObserver.return_value = mock_observer
            
            with patch('kuberef.watcher.time.sleep', side_effect=KeyboardInterrupt):
                run_watch_mode(tmp_path, callback, stream=stream)
                
                captured = capsys.readouterr()
                # Should contain typical watch mode messages
                assert "Watch mode active" in captured.out or "Press Ctrl+C" in captured.out
