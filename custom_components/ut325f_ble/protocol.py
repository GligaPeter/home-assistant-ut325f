"""Pure helpers for the UNI-T UT325F BLE protocol."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime

HEADER = b"\xaa\x55"


def build_frame(message_type: int, payload: bytes = b"") -> bytes:
    """Build an iENV-compatible command frame."""
    length = 1 + len(payload) + 2
    frame = bytearray(HEADER + length.to_bytes(2, "big") + bytes([message_type]) + payload)
    frame.extend((sum(frame) & 0xFFFF).to_bytes(2, "big"))
    return bytes(frame)


def frame_size(buffer: bytes | bytearray) -> int | None:
    """Return the complete frame size described by the header."""
    if len(buffer) < 4 or buffer[:2] != HEADER:
        return None
    return 4 + int.from_bytes(buffer[2:4], "big")


def checksum_valid(frame: bytes) -> bool:
    """Validate the additive checksum used by iENV."""
    return len(frame) >= 7 and (sum(frame[:-2]) & 0xFFFF) == int.from_bytes(
        frame[-2:], "big"
    )


@dataclass(frozen=True)
class PanelSettings:
    live_output: bool
    hold: bool
    bluetooth: bool
    auto_power_off: bool
    logging: bool
    logging_interval: int
    min_max_mode: int
    unit: int
    difference_mode: int
    mains_frequency: int
    battery_level: int
    usb_connected: bool
    backlight: bool

    def writable_payload(self) -> bytes:
        return bytes(
            [
                self.live_output,
                self.hold,
                self.bluetooth,
                self.auto_power_off,
                self.logging,
            ]
        ) + self.logging_interval.to_bytes(4, "big") + bytes(
            [
                self.min_max_mode,
                self.unit,
                self.difference_mode,
                self.mains_frequency,
            ]
        )


def parse_panel_settings(frame: bytes) -> PanelSettings:
    """Parse response type 0x06."""
    if len(frame) < 20 or frame[4] != 0x06:
        raise ValueError("Invalid panel-settings frame")
    return PanelSettings(
        live_output=bool(frame[5]),
        hold=bool(frame[6]),
        bluetooth=bool(frame[7]),
        auto_power_off=bool(frame[8]),
        logging=bool(frame[9]),
        logging_interval=int.from_bytes(frame[10:14], "big"),
        min_max_mode=frame[14],
        unit=frame[15],
        difference_mode=frame[16],
        mains_frequency=frame[17],
        battery_level=frame[18],
        usb_connected=bool(frame[19]),
        backlight=bool(frame[20]) if len(frame) > 20 else False,
    )


@dataclass(frozen=True)
class ChannelSettings:
    probe_types: tuple[int, int, int, int]
    offsets: tuple[float, float, float, float]

    def writable_payload(self) -> bytes:
        types = bytes(0x80 + value for value in self.probe_types)
        offsets = bytes(round(value * 10) & 0xFF for value in self.offsets)
        return types + offsets


def parse_channel_settings(frame: bytes) -> ChannelSettings:
    """Parse response type 0x07."""
    if len(frame) < 15 or frame[4] != 0x07:
        raise ValueError("Invalid channel-settings frame")
    raw_offsets = frame[9:13]
    return ChannelSettings(
        probe_types=tuple(value & 0x0F for value in frame[5:9]),  # type: ignore[arg-type]
        offsets=tuple(
            (value - 256 if value > 127 else value) / 10 for value in raw_offsets
        ),  # type: ignore[arg-type]
    )


@dataclass(frozen=True)
class MemoryRecord:
    timestamp: datetime
    states: tuple[int, int, int, int]
    probe_types: tuple[int, int, int, int]
    temperatures: tuple[float | None, float | None, float | None, float | None]


def parse_memory_page(frame: bytes) -> list[MemoryRecord]:
    """Parse the 32 records in a type 0x02 memory-page response."""
    if len(frame) < 1031 or frame[4] != 0x02:
        raise ValueError("Invalid memory-page frame")
    content = frame[7:1031]
    records: list[MemoryRecord] = []
    for start in range(0, 1024, 32):
        row = content[start : start + 32]
        stored_checksum = int.from_bytes(row[:2], "little")
        if stored_checksum != ((0xAA55 + sum(row[2:])) & 0xFFFF):
            continue
        try:
            timestamp = datetime(
                2000 + row[2], row[3], row[4], row[5], row[6], row[7]
            )
        except ValueError:
            continue
        states = tuple(row[8:12])
        probe_types = tuple(row[12:16])
        values: list[float | None] = []
        for channel in range(4):
            value = struct.unpack_from("<f", row, 16 + channel * 4)[0]
            values.append(round(value, 2) if states[channel] == 0 else None)
        records.append(
            MemoryRecord(
                timestamp=timestamp,
                states=states,  # type: ignore[arg-type]
                probe_types=probe_types,  # type: ignore[arg-type]
                temperatures=tuple(values),  # type: ignore[arg-type]
            )
        )
    return records
