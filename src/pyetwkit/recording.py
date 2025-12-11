"""ETW Recording & Replay (.etwpack format) (v3.0.0 - #51).

This module provides a Python-optimized ETW capture format (.etwpack) for
recording, storing, and replaying ETW sessions.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class CompressionType(Enum):
    """Compression types for .etwpack files."""

    NONE = "none"
    ZSTD = "zstd"
    LZ4 = "lz4"


@dataclass
class RecorderConfig:
    """Configuration for the Recorder."""

    compression: CompressionType = CompressionType.ZSTD
    chunk_size: int = 1024 * 1024  # 1MB
    buffer_size: int = 1024 * 64  # 64KB


@dataclass
class EtwpackHeader:
    """Header for .etwpack files."""

    version: int
    created_at: str
    provider_guids: list[str]
    event_count: int
    duration_ms: int
    compression: str = "zstd"
    schema_version: int = 1

    def to_json(self) -> str:
        """Serialize header to JSON.

        Returns:
            JSON string representation.
        """
        return json.dumps(
            {
                "version": self.version,
                "created_at": self.created_at,
                "provider_guids": self.provider_guids,
                "event_count": self.event_count,
                "duration_ms": self.duration_ms,
                "compression": self.compression,
                "schema_version": self.schema_version,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, json_str: str) -> EtwpackHeader:
        """Deserialize header from JSON.

        Args:
            json_str: JSON string.

        Returns:
            EtwpackHeader instance.
        """
        data = json.loads(json_str)
        return cls(
            version=data["version"],
            created_at=data["created_at"],
            provider_guids=data["provider_guids"],
            event_count=data["event_count"],
            duration_ms=data["duration_ms"],
            compression=data.get("compression", "zstd"),
            schema_version=data.get("schema_version", 1),
        )


@dataclass
class EtwpackChunk:
    """A chunk of events in .etwpack format."""

    chunk_id: int
    event_count: int
    start_timestamp: float
    end_timestamp: float
    data: bytes = field(repr=False)


class EtwpackIndex:
    """Index for fast seeking in .etwpack files."""

    def __init__(self) -> None:
        """Initialize the index."""
        self._entries: list[tuple[float, int]] = []  # (timestamp, offset)

    def add_entry(self, timestamp: float, offset: int) -> None:
        """Add an index entry.

        Args:
            timestamp: Event timestamp.
            offset: File offset.
        """
        self._entries.append((timestamp, offset))

    def find_offset(self, timestamp: float) -> int | None:
        """Find the file offset for a timestamp.

        Args:
            timestamp: Target timestamp.

        Returns:
            File offset or None if not found.
        """
        if not self._entries:
            return None

        # Binary search for closest entry
        left, right = 0, len(self._entries) - 1
        while left < right:
            mid = (left + right) // 2
            if self._entries[mid][0] < timestamp:
                left = mid + 1
            else:
                right = mid

        return self._entries[left][1] if left < len(self._entries) else None


class Recorder:
    """Records ETW events to .etwpack format.

    Example:
        >>> recorder = Recorder("session.etwpack")
        >>> recorder.add_provider("Microsoft-Windows-Kernel-Process")
        >>> with recorder:
        ...     # Events are captured and written to file
        ...     pass
    """

    def __init__(
        self,
        output_path: str | Path,
        config: RecorderConfig | None = None,
    ) -> None:
        """Initialize the Recorder.

        Args:
            output_path: Path to the output .etwpack file.
            config: Optional recorder configuration.
        """
        self._output_path = Path(output_path)
        self._config = config or RecorderConfig()
        self._providers: list[str] = []
        self._is_recording = False
        self._events: list[Any] = []
        self._start_time: datetime | None = None

    @property
    def output_path(self) -> Path:
        """Get the output file path."""
        return self._output_path

    @property
    def providers(self) -> list[str]:
        """Get the list of providers."""
        return list(self._providers)

    @property
    def is_recording(self) -> bool:
        """Check if recording is in progress."""
        return self._is_recording

    def add_provider(self, provider_guid: str) -> Recorder:
        """Add a provider to record.

        Args:
            provider_guid: Provider GUID string.

        Returns:
            Self for method chaining.
        """
        self._providers.append(provider_guid)
        return self

    def start(self) -> Recorder:
        """Start recording.

        Returns:
            Self for method chaining.
        """
        if self._is_recording:
            return self

        self._is_recording = True
        self._start_time = datetime.now()
        self._events = []
        return self

    def stop(self) -> Recorder:
        """Stop recording and write to file.

        Returns:
            Self for method chaining.
        """
        if not self._is_recording:
            return self

        self._is_recording = False
        self._write_file()
        return self

    def add_event(self, event: Any) -> None:
        """Add an event to the recording.

        Args:
            event: ETW event to record.
        """
        if self._is_recording:
            self._events.append(event)

    def _write_file(self) -> None:
        """Write the recorded events to file."""
        if not self._events:
            return

        end_time = datetime.now()
        duration_ms = int((end_time - (self._start_time or end_time)).total_seconds() * 1000)

        header = EtwpackHeader(
            version=1,
            created_at=self._start_time.isoformat() if self._start_time else "",
            provider_guids=self._providers,
            event_count=len(self._events),
            duration_ms=duration_ms,
            compression=self._config.compression.value,
        )

        # For now, write a simple JSON format
        # In production, would use proper binary format with compression
        data = {
            "header": json.loads(header.to_json()),
            "events": [
                {
                    "event_id": getattr(e, "event_id", 0),
                    "provider_name": getattr(e, "provider_name", ""),
                    "timestamp": getattr(e, "timestamp", 0),
                    "process_id": getattr(e, "process_id", 0),
                    "properties": getattr(e, "properties", {}),
                }
                for e in self._events
            ],
        }

        self._output_path.write_text(json.dumps(data, indent=2))

    def __enter__(self) -> Recorder:
        """Context manager entry."""
        return self.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Context manager exit."""
        self.stop()
        return False


class Player:
    """Plays back events from .etwpack files.

    Example:
        >>> player = Player("session.etwpack")
        >>> print(f"Duration: {player.duration}")
        >>> for event in player.events():
        ...     print(event)
    """

    duration: float = 0.0
    event_count: int = 0
    speed: float = 1.0

    def __init__(self, input_path: str | Path) -> None:
        """Initialize the Player.

        Args:
            input_path: Path to the .etwpack file.
        """
        self._input_path = Path(input_path)
        self._header: EtwpackHeader | None = None
        self._events: list[dict[str, Any]] = []
        self._position = 0
        self._load_file()

    def _load_file(self) -> None:
        """Load the .etwpack file."""
        if not self._input_path.exists():
            return

        try:
            data = json.loads(self._input_path.read_text())
            self._header = EtwpackHeader.from_json(json.dumps(data["header"]))
            self._events = data.get("events", [])
            self.duration = self._header.duration_ms / 1000.0
            self.event_count = self._header.event_count
        except (json.JSONDecodeError, KeyError):
            pass

    def seek(self, timestamp: str | float | None = None, position: int | None = None) -> Player:
        """Seek to a position in the recording.

        Args:
            timestamp: Target timestamp (ISO format string or Unix timestamp).
            position: Target event position.

        Returns:
            Self for method chaining.
        """
        if position is not None:
            self._position = max(0, min(position, len(self._events)))
        elif timestamp is not None:
            # Find event closest to timestamp
            target = float(timestamp) if isinstance(timestamp, (int, float)) else 0
            for i, event in enumerate(self._events):
                if event.get("timestamp", 0) >= target:
                    self._position = i
                    break
        return self

    def events(
        self,
        provider: str | None = None,
        event_id: int | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Iterate over events with optional filtering.

        Args:
            provider: Filter by provider name.
            event_id: Filter by event ID.
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Yields:
            Event dictionaries.
        """
        for event in self._events[self._position :]:
            # Apply filters
            if provider and event.get("provider_name") != provider:
                continue
            if event_id is not None and event.get("event_id") != event_id:
                continue
            if start_time and event.get("timestamp", 0) < start_time:
                continue
            if end_time and event.get("timestamp", 0) > end_time:
                continue

            yield event


def convert_etl_to_etwpack(
    source: str | Path,
    destination: str | Path,
    compression: CompressionType = CompressionType.ZSTD,
) -> None:
    """Convert ETL file to .etwpack format.

    Args:
        source: Path to source ETL file.
        destination: Path to destination .etwpack file.
        compression: Compression type to use.
    """
    # This would use the ETL reader to convert
    # For now, just create an empty etwpack file
    etl_path = Path(source)
    etwpack_path = Path(destination)

    if not etl_path.exists():
        raise FileNotFoundError(f"ETL file not found: {etl_path}")

    header = EtwpackHeader(
        version=1,
        created_at=datetime.now().isoformat(),
        provider_guids=[],
        event_count=0,
        duration_ms=0,
        compression=compression.value,
    )

    data = {"header": json.loads(header.to_json()), "events": []}

    etwpack_path.write_text(json.dumps(data, indent=2))


def record_command(
    output: str,
    providers: list[str],
    duration: int | None = None,
    profile: str | None = None,
) -> None:
    """CLI command handler for recording.

    Args:
        output: Output file path.
        providers: List of provider GUIDs.
        duration: Recording duration in seconds.
        profile: Provider profile name.
    """
    _ = duration  # Will be used when implementing timed recording
    _ = profile  # Will be used when implementing provider profiles
    recorder = Recorder(output)
    for provider in providers:
        recorder.add_provider(provider)


def replay_command(
    input_file: str,
    provider: str | None = None,
    speed: float = 1.0,
) -> None:
    """CLI command handler for replay.

    Args:
        input_file: Input .etwpack file path.
        provider: Optional provider filter.
        speed: Playback speed multiplier.
    """
    _ = speed  # Will be used when implementing timed playback
    player = Player(input_file)
    for event in player.events(provider=provider):
        print(event)


def convert_command(
    source: str,
    destination: str,
) -> None:
    """CLI command handler for conversion.

    Args:
        source: Source ETL file path.
        destination: Destination .etwpack file path.
    """
    convert_etl_to_etwpack(source, destination)
