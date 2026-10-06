from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import UT325FEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [UT325FLoggingInterval(coordinator, entry)]
    entities.extend(UT325FOffset(coordinator, entry, channel) for channel in range(4))
    async_add_entities(entities)


class UT325FLoggingInterval(UT325FEntity, NumberEntity):
    _attr_name = "Logging interval"
    _attr_native_min_value = 1
    _attr_native_max_value = 86400
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.unique_id}_logging_interval_number"

    @property
    def native_value(self):
        panel = self.coordinator.panel_settings
        return panel.logging_interval if panel else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_panel_field("logging_interval", int(value))


class UT325FOffset(UT325FEntity, NumberEntity):
    _attr_native_min_value = -5
    _attr_native_max_value = 5
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry, channel: int) -> None:
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"T{channel + 1} offset"
        self._attr_unique_id = f"{entry.unique_id}_t{channel + 1}_offset"

    @property
    def native_value(self):
        settings = self.coordinator.channel_settings
        return settings.offsets[self._channel] if settings else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_channel_field(self._channel, "offsets", round(value, 1))
