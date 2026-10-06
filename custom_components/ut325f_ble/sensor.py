from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
    async_add_entities(UT325FSensor(coordinator, entry, i) for i in range(4))


class UT325FSensor(CoordinatorEntity[UT325FCoordinator], SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, entry, channel: int) -> None:
        super().__init__(coordinator)
        self._channel = channel
        self._attr_name = f"UT325F T{channel + 1}"
        self._attr_unique_id = f"{entry.unique_id}_t{channel + 1}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name="UNI-T UT325F",
            manufacturer="UNI-T",
            model="UT325F",
        )

    @property
    def native_value(self):
        return self.coordinator.data[self._channel]
