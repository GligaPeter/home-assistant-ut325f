from __future__ import annotations

import asyncio
import logging
import struct
from datetime import timedelta

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import FRAME_HEADER, FRAME_SIZE, NOTIFY_UUID, WRITE_UUID

_LOGGER = logging.getLogger(__name__)


class UT325FCoordinator(DataUpdateCoordinator[list[float | None]]):
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
        self._latest: list[float | None] | None = None

    def _notification(self, _sender, payload: bytearray) -> None:
        self._buffer.extend(payload)
        while True:
            start = self._buffer.find(FRAME_HEADER)
            if start < 0:
                self._buffer[:] = self._buffer[-4:]
                return
            if len(self._buffer) - start < FRAME_SIZE:
                if start:
                    del self._buffer[:start]
                return
            frame = bytes(self._buffer[start : start + FRAME_SIZE])
            del self._buffer[: start + FRAME_SIZE]
            statuses = frame[21:25]
            values: list[float | None] = []
            for channel in range(4):
                if statuses[channel] == 0x30:
                    values.append(None)
                    continue
                value = struct.unpack_from("<f", frame, 5 + channel * 4)[0]
                values.append(round(value, 2) if -300 <= value <= 2000 else None)
            self._latest = values
            self._frame_event.set()

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

    async def _async_update_data(self) -> list[float | None]:
        try:
            await self._connect()
            self._frame_event.clear()
            await self._client.write_gatt_char(WRITE_UUID, b"\x5e", response=False)
            await asyncio.wait_for(self._frame_event.wait(), timeout=4)
            if self._latest is None:
                raise UpdateFailed("Nem érkezett értelmezhető mérési adat")
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

    async def async_shutdown(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
