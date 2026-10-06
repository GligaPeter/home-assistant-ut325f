from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.network import get_url

from .const import DOMAIN


class UT325FEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name="UNI-T UT325F",
            manufacturer="UNI-T",
            model="UT325F",
            configuration_url=(
                f"{get_url(coordinator.hass, prefer_external=False)}"
                "/local/ut325f-memory-latest.zip"
            ),
        )
