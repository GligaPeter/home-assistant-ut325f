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
    entities = [UT325FSwitch(coordinator, entry, key, name) for key, name in FIELDS.items()]
    entities.append(UT325FMemoryEraseArmSwitch(coordinator, entry))
    async_add_entities(entities)


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


class UT325FMemoryEraseArmSwitch(UT325FEntity, SwitchEntity):
    _attr_name = "Enable memory erase (30 seconds)"
    _attr_icon = "mdi:shield-alert"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.unique_id}_memory_erase_arm"

    @property
    def is_on(self):
        return self.coordinator.memory_erase_armed

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_arm_memory_erase(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_arm_memory_erase(False)
