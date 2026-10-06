from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, THERMOCOUPLE_TYPES
from .entity import UT325FEntity

PANEL_SELECTS = {
    "unit": ("Display unit", ["°C", "°F", "K"]),
    "min_max_mode": ("MIN/MAX mode", ["normal", "maximum", "minimum", "average"]),
    "difference_mode": ("Difference mode", ["normal", "T1", "T2", "T3", "T4"]),
    "mains_frequency": ("Mains filter", ["50 Hz", "60 Hz"]),
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        UT325FPanelSelect(coordinator, entry, field, name, options)
        for field, (name, options) in PANEL_SELECTS.items()
    ]
    entities.extend(UT325FProbeSelect(coordinator, entry, channel) for channel in range(4))
    async_add_entities(entities)


class UT325FPanelSelect(UT325FEntity, SelectEntity):
    def __init__(self, coordinator, entry, field, name, options) -> None:
        super().__init__(coordinator, entry)
        self._field = field
        self._attr_name = name
        self._attr_options = options
        self._attr_unique_id = f"{entry.unique_id}_{field}_select"

    @property
    def current_option(self):
        panel = self.coordinator.panel_settings
        if panel is None:
            return None
        value = getattr(panel, self._field)
        return self.options[value] if 0 <= value < len(self.options) else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_panel_field(self._field, self.options.index(option))


class UT325FProbeSelect(UT325FEntity, SelectEntity):
    _attr_options = list(THERMOCOUPLE_TYPES.values())
    _attr_icon = "mdi:thermometer-probe"

    def __init__(self, coordinator, entry, channel: int) -> None:
        super().__init__(coordinator, entry)
        self._channel = channel
        self._attr_name = f"T{channel + 1} thermocouple type"
        self._attr_unique_id = f"{entry.unique_id}_t{channel + 1}_type_select"

    @property
    def current_option(self):
        settings = self.coordinator.channel_settings
        return THERMOCOUPLE_TYPES.get(settings.probe_types[self._channel]) if settings else None

    async def async_select_option(self, option: str) -> None:
        code = next(key for key, value in THERMOCOUPLE_TYPES.items() if value == option)
        await self.coordinator.async_set_channel_field(self._channel, "probe_types", code)
