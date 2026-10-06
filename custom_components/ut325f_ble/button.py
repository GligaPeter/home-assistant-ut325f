from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import UT325FEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            UT325FDownloadButton(coordinator, entry),
            UT325FSyncClockButton(coordinator, entry),
            UT325FClearMemoryButton(coordinator, entry),
        ]
    )


class UT325FDownloadButton(UT325FEntity, ButtonEntity):
    _attr_name = "Download measurement memory"
    _attr_icon = "mdi:download"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.unique_id}_download_memory"

    async def async_press(self) -> None:
        await self.coordinator.async_download_memory()


class UT325FSyncClockButton(UT325FEntity, ButtonEntity):
    _attr_name = "Synchronize clock"
    _attr_icon = "mdi:clock-sync"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.unique_id}_sync_clock"

    async def async_press(self) -> None:
        await self.coordinator.async_sync_clock()


class UT325FClearMemoryButton(UT325FEntity, ButtonEntity):
    _attr_name = "Erase internal memory"
    _attr_icon = "mdi:delete-alert"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.unique_id}_clear_memory"

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.memory_erase_armed

    async def async_press(self) -> None:
        await self.coordinator.async_clear_memory()
