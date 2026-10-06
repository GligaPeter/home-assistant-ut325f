from __future__ import annotations

import asyncio
import csv
import logging
import math
import struct
from dataclasses import dataclass, replace
from pathlib import Path
from datetime import datetime, timedelta

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CHANNEL_STATES,
    FRAME_HEADER,
    FRAME_SIZE,
    NOTIFY_UUID,
    THERMOCOUPLE_TYPES,
    WRITE_UUID,
)
from .protocol import (
    ChannelSettings,
    PanelSettings,
    build_frame,
    frame_size,
    parse_channel_settings,
    parse_memory_page,
    parse_panel_settings,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class UT325FData:
    temperatures: tuple[float | None, ...]
    channel_states: tuple[str, ...]
    thermocouple_types: tuple[str, ...]


def parse_live_frame(frame: bytes) -> UT325FData:
    """Decode the fields confirmed by the vendor application."""
    if len(frame) < 34 or not frame.startswith(FRAME_HEADER):
        raise ValueError("Invalid UT325F live-data frame")

    status_bytes = frame[21:25]
    temperatures: list[float | None] = []
    states: list[str] = []
    probe_types: list[str] = []

    for channel, status_byte in enumerate(status_bytes):
        state_code = (status_byte >> 4) & 0x0F
        state = CHANNEL_STATES.get(state_code, "unknown")
        value = struct.unpack_from("<f", frame, 5 + channel * 4)[0]
        temperatures.append(
            round(value, 2) if state == "ok" and -300 <= value <= 2000 else None
        )
        states.append(state)
        probe_types.append(THERMOCOUPLE_TYPES.get(status_byte & 0x0F, "unknown"))

    return UT325FData(
        temperatures=tuple(temperatures),
        channel_states=tuple(states),
        thermocouple_types=tuple(probe_types),
    )


class UT325FCoordinator(DataUpdateCoordinator[UT325FData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="UNI-T UT325F",
            update_interval=timedelta(seconds=5),
        )
        self.address = entry.unique_id or entry.data["address"]
        self._client: BleakClient | None = None
        self._buffer = bytearray()
        self._frame_event = asyncio.Event()
        self._latest: UT325FData | None = None
        self._request_lock = asyncio.Lock()
        self._pending: dict[int, asyncio.Future[bytes]] = {}
        self._memory_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.panel_settings: PanelSettings | None = None
        self.channel_settings: ChannelSettings | None = None
        self.used_records: int | None = None
        self.device_name: str | None = None
        self.firmware_version: str | None = None
        self._metadata_counter = 0
        self.last_memory_download_url: str | None = None
        self.last_memory_download_records: int | None = None

    def _notification(self, _sender, payload: bytearray) -> None:
        self._buffer.extend(payload)
        while True:
            start = self._buffer.find(b"\xaa\x55")
            if start < 0:
                self._buffer[:] = self._buffer[-1:]
                return
            if start:
                del self._buffer[:start]
            total = frame_size(self._buffer)
            if total is None or len(self._buffer) < total:
                # The legacy 0x5E response was observed without all trailing bytes.
                if self._buffer.startswith(FRAME_HEADER) and len(self._buffer) >= FRAME_SIZE:
                    total = FRAME_SIZE
                else:
                    return
            frame = bytes(self._buffer[:total])
            del self._buffer[:total]
            if len(frame) < 5:
                continue
            message_type = frame[4]
            if message_type == 0x02:
                self._memory_queue.put_nowait(frame)
            pending = self._pending.pop(message_type, None)
            if pending is not None and not pending.done():
                pending.set_result(frame)
            if message_type != 0x01:
                continue
            try:
                self._latest = parse_live_frame(frame)
            except ValueError:
                _LOGGER.debug("Nem értelmezhető UT325F adatkeret", exc_info=True)
                continue
            self._frame_event.set()

    async def async_request(
        self, command: int, response_type: int, payload: bytes = b"", timeout: float = 8
    ) -> bytes:
        """Send an iENV command and wait for its response frame."""
        async with self._request_lock:
            await self._connect()
            future = self.hass.loop.create_future()
            self._pending[response_type] = future
            try:
                await self._client.write_gatt_char(
                    WRITE_UUID, build_frame(command, payload), response=False
                )
                return await asyncio.wait_for(future, timeout)
            finally:
                self._pending.pop(response_type, None)

    async def async_sync_clock(self) -> None:
        """Set the meter clock to Home Assistant local time."""
        now = datetime.now().astimezone()
        payload = bytes(
            [now.year % 100, now.month, now.day, now.hour, now.minute, now.second]
        )
        async with self._request_lock:
            await self._connect()
            await self._client.write_gatt_char(
                WRITE_UUID, build_frame(0x31, payload), response=False
            )

    async def async_download_memory(self) -> tuple[str, int]:
        """Download the meter memory and export it under /config/www."""
        count_frame = await self.async_request(0x33, 0x05)
        used_count = int.from_bytes(count_frame[5:9], "big")
        page_count = math.ceil(used_count / 32)
        records = []
        panel = self.panel_settings
        if panel is None:
            panel = parse_panel_settings(await self.async_request(0x35, 0x06))
            self.panel_settings = panel

        stopped = replace(panel, live_output=False)
        async with self._request_lock:
            await self._connect()
            while not self._memory_queue.empty():
                self._memory_queue.get_nowait()
            await self._client.write_gatt_char(
                WRITE_UUID, build_frame(0x36, stopped.writable_payload()), response=False
            )
            await asyncio.sleep(0.6)
            try:
                payload = (0).to_bytes(2, "big") + page_count.to_bytes(2, "big")
                await self._client.write_gatt_char(
                    WRITE_UUID, build_frame(0x32, payload), response=False
                )
                pages: dict[int, bytes] = {}
                while len(pages) < page_count:
                    frame = await asyncio.wait_for(self._memory_queue.get(), timeout=8)
                    pages[int.from_bytes(frame[5:7], "big")] = frame
                for page in sorted(pages):
                    records.extend(parse_memory_page(pages[page]))
            finally:
                await self._client.write_gatt_char(
                    WRITE_UUID, build_frame(0x36, panel.writable_payload()), response=False
                )

        stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        target = Path(self.hass.config.path("www", f"ut325f-memory-{stamp}.csv"))

        def _write_csv() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", newline="", encoding="utf-8") as output:
                writer = csv.writer(output)
                writer.writerow(
                    ["timestamp", "t1_c", "t2_c", "t3_c", "t4_c", "t1_type", "t2_type", "t3_type", "t4_type"]
                )
                for record in records[:used_count]:
                    writer.writerow(
                        [record.timestamp.isoformat(), *record.temperatures, *record.probe_types]
                    )

        await self.hass.async_add_executor_job(_write_csv)
        self.last_memory_download_url = f"/local/{target.name}"
        self.last_memory_download_records = min(len(records), used_count)
        self.async_update_listeners()
        return self.last_memory_download_url, self.last_memory_download_records

    async def async_send_confirmed_command(self, command: int) -> None:
        """Send a command whose confirmation is handled by the HA service schema."""
        async with self._request_lock:
            await self._connect()
            await self._client.write_gatt_char(
                WRITE_UUID, build_frame(command), response=False
            )

    async def async_send_payload(self, command: int, payload: bytes) -> None:
        """Send a verified iENV settings command."""
        async with self._request_lock:
            await self._connect()
            await self._client.write_gatt_char(
                WRITE_UUID, build_frame(command, payload), response=False
            )

    async def async_set_panel_field(self, field: str, value) -> None:
        if self.panel_settings is None:
            await self._async_refresh_metadata()
        if self.panel_settings is None:
            raise UpdateFailed("A panelbeállítások nem olvashatók")
        updated = replace(self.panel_settings, **{field: value})
        await self.async_send_payload(0x36, updated.writable_payload())
        self.panel_settings = updated
        self.async_update_listeners()

    async def async_set_channel_field(self, channel: int, field: str, value) -> None:
        if self.channel_settings is None:
            await self._async_refresh_metadata()
        if self.channel_settings is None:
            raise UpdateFailed("A csatornabeállítások nem olvashatók")
        values = list(getattr(self.channel_settings, field))
        values[channel] = value
        updated = replace(self.channel_settings, **{field: tuple(values)})
        await self.async_send_payload(0x38, updated.writable_payload())
        self.channel_settings = updated
        self.async_update_listeners()

    async def _connect(self) -> None:
        if self._client and self._client.is_connected:
            return
        device = async_ble_device_from_address(self.hass, self.address, connectable=True)
        if device is None:
            raise UpdateFailed("A UT325F jelenleg nem érhető el Bluetoothon")
        self._client = await establish_connection(
            BleakClient, device, device.name or "UT325F", max_attempts=3
        )
        await self._client.start_notify(NOTIFY_UUID, self._notification)

    async def _async_update_data(self) -> UT325FData:
        try:
            async with self._request_lock:
                await self._connect()
                self._frame_event.clear()
                await self._client.write_gatt_char(WRITE_UUID, b"\x5e", response=False)
                await asyncio.wait_for(self._frame_event.wait(), timeout=4)
            if self._latest is None:
                raise UpdateFailed("Nem érkezett értelmezhető mérési adat")
            self._metadata_counter += 1
            if self._metadata_counter == 1 or self._metadata_counter % 12 == 0:
                await self._async_refresh_metadata()
            return self._latest
        except UpdateFailed:
            raise
        except Exception as err:
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None
            raise UpdateFailed(f"UT325F Bluetooth-hiba: {err}") from err

    async def _async_refresh_metadata(self) -> None:
        """Refresh the read-only settings exposed by the iENV application."""
        try:
            self.panel_settings = parse_panel_settings(
                await self.async_request(0x35, 0x06)
            )
            self.channel_settings = parse_channel_settings(
                await self.async_request(0x37, 0x07)
            )
            used = await self.async_request(0x33, 0x05)
            self.used_records = int.from_bytes(used[5:9], "big")
            info = await self.async_request(0x00, 0x00)
            if len(info) >= 27:
                self.device_name = info[5:25].split(b"\x00", 1)[0].decode(
                    "ascii", errors="replace"
                )
                self.firmware_version = f"{info[25]}.{info[26]}"
        except Exception as err:
            _LOGGER.debug("UT325F metadata refresh failed: %s", err)

    async def async_shutdown(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
