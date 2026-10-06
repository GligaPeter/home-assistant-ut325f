from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import UT325FEntity

FIELDS = {
    "bluetooth": "Bluetooth",
    "usb_connected": "USB connected",
    "backlight": "Backlight",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(UT325FBinarySensor(coordinator, entry, key, name) for key, name in FIELDS.items())


class UT325FBinarySensor(UT325FEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, field: str, name: str) -> None:
        super().__init__(coordinator, entry)
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{entry.unique_id}_{field}_status"

    @property
    def is_on(self):
        panel = self.coordinator.panel_settings
        return getattr(panel, self._field) if panel else None
