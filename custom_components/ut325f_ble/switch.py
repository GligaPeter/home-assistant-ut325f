from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import UT325FEntity

FIELDS = {
    "hold": "HOLD",
    "auto_power_off": "Automatic power off",
    "logging": "Internal logging",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(UT325FSwitch(coordinator, entry, key, name) for key, name in FIELDS.items())


class UT325FSwitch(UT325FEntity, SwitchEntity):
    def __init__(self, coordinator, entry, field: str, name: str) -> None:
        super().__init__(coordinator, entry)
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{entry.unique_id}_{field}"

    @property
    def is_on(self):
        panel = self.coordinator.panel_settings
        return getattr(panel, self._field) if panel else None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_panel_field(self._field, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_panel_field(self._field, False)
