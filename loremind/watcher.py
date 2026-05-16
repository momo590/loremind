"""File watcher — monitors GM session notes files/folders for changes."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileModifiedEvent, FileCreatedEvent, PatternMatchingEventHandler
from watchdog.observers import Observer


class SessionNotesHandler(PatternMatchingEventHandler):
    """Fires callback when a watched notes file changes."""

    def __init__(self, callback: Callable[[Path], None], patterns: list[str]):
        super().__init__(patterns=patterns, ignore_directories=True, case_sensitive=False)
        self._callback = callback
        self._last_fired: dict[str, float] = {}
        self._debounce_s = 3.0  # avoid firing on every keystroke

    def on_modified(self, event: FileModifiedEvent) -> None:
        self._fire(Path(event.src_path))

    def on_created(self, event: FileCreatedEvent) -> None:
        self._fire(Path(event.src_path))

    def _fire(self, path: Path) -> None:
        now = time.monotonic()
        key = str(path)
        if now - self._last_fired.get(key, 0) < self._debounce_s:
            return
        self._last_fired[key] = now
        self._callback(path)


class NotesWatcher:
    """Watch one or more files/folders for session note changes."""

    def __init__(self, callback: Callable[[Path], None]):
        self._callback = callback
        self._observer = Observer()
        self._started = False

    def add(self, path: Path) -> None:
        """Add a file or folder to watch."""
        if path.is_file():
            watch_dir = path.parent
            patterns = [f"*{path.suffix}" if path.suffix else path.name]
        else:
            watch_dir = path
            patterns = ["*.md", "*.txt", "*.rtf"]

        handler = SessionNotesHandler(callback=self._callback, patterns=patterns)
        self._observer.schedule(handler, str(watch_dir), recursive=False)

    def start(self) -> None:
        if not self._started:
            self._observer.start()
            self._started = True

    def stop(self) -> None:
        if self._started:
            self._observer.stop()
            self._observer.join()
            self._started = False


# iCloud Drive scanner — watches the Loremind scan folder for new images
ICLOUD_SCAN_DIR = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Loremind" / "scans"


class ICloudScanWatcher:
    """Watch ~/iCloud Drive/Loremind/scans/ for new images (iPhone document scans)."""

    IMAGE_PATTERNS = ["*.jpg", "*.jpeg", "*.png", "*.heic", "*.pdf"]

    def __init__(self, callback: Callable[[Path], None], scan_dir: Optional[Path] = None):
        self._callback = callback
        self._scan_dir = scan_dir or ICLOUD_SCAN_DIR
        self._watcher = NotesWatcher(callback=self._on_image)

    def _on_image(self, path: Path) -> None:
        if path.suffix.lower().lstrip(".") in ("jpg", "jpeg", "png", "heic", "pdf"):
            self._callback(path)

    def start(self) -> None:
        if not self._scan_dir.exists():
            self._scan_dir.mkdir(parents=True, exist_ok=True)
        self._watcher.add(self._scan_dir)
        self._watcher.start()

    def stop(self) -> None:
        self._watcher.stop()
