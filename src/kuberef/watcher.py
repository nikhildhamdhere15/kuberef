import time
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
from watchdog.observers import Observer

console = Console()

YAML_SUFFIXES = {".yaml", ".yml"}


class YamlAuditHandler(FileSystemEventHandler):
    """This Triggers a re-audit whenever a .yaml/.yml file is modified or created."""

    def __init__(self, audit_callback: Callable[[Path], None], cooldown_seconds: float = 1.5, stream=None):
        super().__init__()
        self.audit_callback = audit_callback
        self.cooldown_seconds = cooldown_seconds
        self.last_executed = {}
        self.stream = stream

    def _is_yaml(self, path: str) -> bool:
        return Path(path).suffix.lower() in YAML_SUFFIXES

    def _handle_event(self, event_path: str, event_type: str):
        if not self._is_yaml(event_path):
            return
            
        current_time = time.time()
        last_time = self.last_executed.get(event_path, -float('inf'))
        
        if current_time - last_time >= self.cooldown_seconds:
            self.last_executed[event_path] = current_time
            
            # Emit NDJSON event if streaming is enabled
            if self.stream and self.stream.enabled:
                self.stream.emit_change_detected(event_path, event_type)
            else:
                # Display human-readable output only when NDJSON streaming is disabled
                if event_type == "modified":
                    console.print(f"\n[bold blue]⟳ Change detected:[/bold blue] {event_path}")
                elif event_type == "created":
                    console.print(f"\n[bold blue]⟳ New file detected:[/bold blue] {event_path}")
            
            self.audit_callback(Path(event_path))

    def on_modified(self, event):
        if not event.is_directory:
            self._handle_event(event.src_path, "modified")

    def on_created(self, event):
        if not event.is_directory:
            self._handle_event(event.src_path, "created")


def run_watch_mode(watch_path: Path, audit_callback: Callable[[Path], None], stream=None) -> None:
    """
    - Starts the filesystem watcher on watch_path.
    - Calls audit_callback(path) on every .yaml/.yml change/create.
    - Blocks until Ctrl+C.
    - Emits NDJSON events if stream is provided and enabled.
    """
    # Determine what to watch — always watch the directory
    watch_dir = watch_path if watch_path.is_dir() else watch_path.parent

    handler = YamlAuditHandler(audit_callback, stream=stream)
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=True)
    observer.start()

    # Display watch mode message only if NDJSON streaming is disabled
    if not (stream and stream.enabled):
        console.print(f"\n[bold green]Watch mode active.[/bold green] Monitoring: [cyan]{watch_dir}[/cyan]")
        console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if not (stream and stream.enabled):
            console.print("\n[bold yellow]Watch mode stopped.[/bold yellow]")

    observer.join()
