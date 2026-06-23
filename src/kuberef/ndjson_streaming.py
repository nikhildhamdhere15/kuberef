"""NDJSON (Newline-Delimited JSON) event streaming for watch mode."""

import json
import sys
from typing import Any, Dict
from datetime import datetime


class NDJSONEventStream:
    """Manages NDJSON event streaming for watch mode."""

    def __init__(self, enabled: bool = False):
        """
        Initialize NDJSON streaming.
        
        Args:
            enabled: True if both --watch and --json flags are active
        """
        self.enabled = enabled

    def emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Emit a single-line NDJSON event.
        
        Args:
            event_type: Type of event (e.g., 'watcher_started', 'change_detected', 'audit_summary')
            data: Event payload dictionary
        """
        if not self.enabled:
            return

        event = {"event": event_type, "timestamp": datetime.utcnow().isoformat()}
        event.update(data)
        
        # Print as single-line JSON (no indentation)
        print(json.dumps(event, separators=(',', ':'), default=str))
        sys.stdout.flush()  # Ensure immediate output for streaming

    def emit_watcher_started(self, watch_path: str) -> None:
        """Emit watcher_started event."""
        self.emit_event("watcher_started", {"watch_path": watch_path})

    def emit_change_detected(self, file_path: str, change_type: str) -> None:
        """
        Emit change_detected event.
        
        Args:
            file_path: Path to the changed file
            change_type: Type of change ('modified' or 'created')
        """
        self.emit_event("change_detected", {"file_path": file_path, "change_type": change_type})

    def emit_audit_summary(self, summary: Dict[str, Any]) -> None:
        """Emit audit_summary event with flattened audit results."""
        self.emit_event("audit_summary", summary)

    def emit_watcher_stopped(self) -> None:
        """Emit watcher_stopped event."""
        self.emit_event("watcher_stopped", {})
