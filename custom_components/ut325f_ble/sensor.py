from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UT325FCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        UT325FTemperatureSensor(coordinator, entry, i) for i in range(4)
    ]
    entities.extend(UT325FProbeTypeSensor(coordinator, entry, i) for i in range(4))
    entities.extend(UT325FChannelStateSensor(coordinator, entry, i) for i in range(4))
    entities.extend(
        [
            UT325FMetadataSensor(coordinator, entry, "memory", "Stored records"),
            UT325FMetadataSensor(coordinator, entry, "battery", "Battery level"),
            UT325FMetadataSensor(coordinator, entry, "firmware", "Firmware version"),
            UT325FMetadataSensor(coordinator, entry, "unit", "Display unit"),
            UT325FMetadataSensor(coordinator, entry, "mode", "MIN/MAX mode"),
            UT325FMetadataSensor(coordinator, entry, "difference", "Difference mode"),
            UT325FMetadataSensor(coordinator, entry, "frequency", "Mains filter"),
            UT325FMetadataSensor(coordinator, entry, "interval", "Logging interval"),
            UT325FMetadataSensor(coordinator, entry, "export", "Last memory export"),
        ]
    )
    async_add_entities(entities)


class UT325FBaseSensor(CoordinatorEntity[UT325FCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name="UNI-T UT325F",
            manufacturer="UNI-T",
            model="UT325F",
        )


class UT325FTemperatureSensor(UT325FBaseSensor):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, entry, channel: int) -> None:
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"T{channel + 1}"
        self._attr_unique_id = f"{entry.unique_id}_t{channel + 1}"

    @property
    def native_value(self):
        return self.coordinator.data.temperatures[self._channel]

    @property
    def extra_state_attributes(self):
        return {
            "channel_state": self.coordinator.data.channel_states[self._channel],
            "thermocouple_type": self.coordinator.data.thermocouple_types[
                self._channel
            ],
        }


class UT325FProbeTypeSensor(UT325FBaseSensor):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["K", "J", "T", "E", "R", "S", "N", "B", "unknown"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:thermometer-probe"

    def __init__(self, coordinator, entry, channel: int) -> None:
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"T{channel + 1} probe type"
        self._attr_unique_id = f"{entry.unique_id}_t{channel + 1}_probe_type"

    @property
    def native_value(self):
        return self.coordinator.data.thermocouple_types[self._channel]


class UT325FChannelStateSensor(UT325FBaseSensor):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ok", "under_range", "over_range", "disconnected", "unknown"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:connection"

    def __init__(self, coordinator, entry, channel: int) -> None:
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"T{channel + 1} status"
        self._attr_unique_id = f"{entry.unique_id}_t{channel + 1}_status"

    @property
    def native_value(self):
        return self.coordinator.data.channel_states[self._channel]


class UT325FMetadataSensor(UT325FBaseSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, key: str, name: str) -> None:
        super().__init__(coordinator, entry)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.unique_id}_{key}"

    @property
    def native_value(self):
        panel = self.coordinator.panel_settings
        if self._key == "memory":
            return self.coordinator.used_records
        if self._key == "firmware":
            return self.coordinator.firmware_version
        if self._key == "export":
            return self.coordinator.last_memory_download_url
        if panel is None:
            return None
        values = {
            "battery": panel.battery_level,
            "unit": {0: "°C", 1: "°F", 2: "K"}.get(panel.unit, "unknown"),
            "mode": {0: "normal", 1: "maximum", 2: "minimum", 3: "average"}.get(panel.min_max_mode, "unknown"),
            "difference": {0: "normal", 1: "T1", 2: "T2", 3: "T3", 4: "T4"}.get(panel.difference_mode, "unknown"),
            "frequency": "60 Hz" if panel.mains_frequency else "50 Hz",
            "interval": panel.logging_interval,
        }
        return values[self._key]

    @property
    def extra_state_attributes(self):
        panel = self.coordinator.panel_settings
        if self._key != "battery" or panel is None:
            return None
        return {
            "hold": panel.hold,
            "bluetooth": panel.bluetooth,
            "auto_power_off": panel.auto_power_off,
            "logging": panel.logging,
            "usb_connected": panel.usb_connected,
            "backlight": panel.backlight,
        }
