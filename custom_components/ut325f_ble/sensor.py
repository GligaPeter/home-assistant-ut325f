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
    entities.append(UT325FAmbientTemperatureSensor(coordinator, entry))
    entities.extend(UT325FProbeTypeSensor(coordinator, entry, i) for i in range(4))
    entities.extend(UT325FChannelStateSensor(coordinator, entry, i) for i in range(4))
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


class UT325FAmbientTemperatureSensor(UT325FBaseSensor):
    _attr_name = "Internal temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.unique_id}_internal_temperature"

    @property
    def native_value(self):
        return self.coordinator.data.ambient_temperature


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
