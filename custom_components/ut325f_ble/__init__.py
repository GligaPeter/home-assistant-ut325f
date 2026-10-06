from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
import voluptuous as vol
from dataclasses import replace

from .const import DOMAIN
from .coordinator import UT325FCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


def _coordinator_for_call(hass: HomeAssistant, call: ServiceCall) -> UT325FCoordinator:
    coordinators = hass.data.get(DOMAIN, {})
    entry_id = call.data.get("config_entry_id")
    if entry_id:
        return coordinators[entry_id]
    if len(coordinators) != 1:
        raise ValueError("config_entry_id is required when multiple UT325F devices exist")
    return next(iter(coordinators.values()))


async def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "sync_clock"):
        return

    schema = vol.Schema({vol.Optional("config_entry_id"): str})

    async def sync_clock(call: ServiceCall) -> None:
        await _coordinator_for_call(hass, call).async_sync_clock()

    async def destructive(call: ServiceCall) -> None:
        if call.data.get("confirm") is not True:
            raise ValueError("Set confirm to true to run this destructive action")
        command = 0x34 if call.service == "clear_memory" else 0x3B
        await _coordinator_for_call(hass, call).async_send_confirmed_command(command)

    async def set_panel_settings(call: ServiceCall) -> None:
        coordinator = _coordinator_for_call(hass, call)
        if coordinator.panel_settings is None:
            await coordinator._async_refresh_metadata()
        current = coordinator.panel_settings
        if current is None:
            raise ValueError("Could not read the current panel settings")
        updates = {key: value for key, value in call.data.items() if key != "config_entry_id"}
        updated = replace(current, **updates)
        await coordinator.async_send_payload(0x36, updated.writable_payload())
        coordinator.panel_settings = updated
        coordinator.async_update_listeners()

    async def set_channel_settings(call: ServiceCall) -> None:
        coordinator = _coordinator_for_call(hass, call)
        if coordinator.channel_settings is None:
            await coordinator._async_refresh_metadata()
        current = coordinator.channel_settings
        if current is None:
            raise ValueError("Could not read the current channel settings")
        probe_types = list(current.probe_types)
        offsets = list(current.offsets)
        for channel in range(4):
            if f"t{channel + 1}_type" in call.data:
                probe_types[channel] = call.data[f"t{channel + 1}_type"]
            if f"t{channel + 1}_offset" in call.data:
                offsets[channel] = call.data[f"t{channel + 1}_offset"]
        updated = replace(current, probe_types=tuple(probe_types), offsets=tuple(offsets))
        await coordinator.async_send_payload(0x38, updated.writable_payload())
        coordinator.channel_settings = updated
        coordinator.async_update_listeners()

    hass.services.async_register(DOMAIN, "sync_clock", sync_clock, schema=schema)
    destructive_schema = vol.Schema(
        {vol.Optional("config_entry_id"): str, vol.Required("confirm"): bool}
    )
    hass.services.async_register(
        DOMAIN, "clear_memory", destructive, schema=destructive_schema
    )
    hass.services.async_register(
        DOMAIN, "factory_reset", destructive, schema=destructive_schema
    )
    panel_fields = {
        vol.Optional("config_entry_id"): str,
        vol.Optional("hold"): bool,
        vol.Optional("bluetooth"): bool,
        vol.Optional("auto_power_off"): bool,
        vol.Optional("logging"): bool,
        vol.Optional("logging_interval"): vol.All(int, vol.Range(min=1)),
        vol.Optional("min_max_mode"): vol.In([0, 1, 2, 3]),
        vol.Optional("unit"): vol.In([0, 1, 2]),
        vol.Optional("difference_mode"): vol.In([0, 1, 2, 3, 4]),
        vol.Optional("mains_frequency"): vol.In([0, 1]),
    }
    hass.services.async_register(
        DOMAIN, "set_panel_settings", set_panel_settings, schema=vol.Schema(panel_fields)
    )
    channel_fields = {vol.Optional("config_entry_id"): str}
    for channel in range(1, 5):
        channel_fields[vol.Optional(f"t{channel}_type")] = vol.In(range(8))
        channel_fields[vol.Optional(f"t{channel}_offset")] = vol.All(
            vol.Coerce(float), vol.Range(min=-5, max=5)
        )
    hass.services.async_register(
        DOMAIN,
        "set_channel_settings",
        set_channel_settings,
        schema=vol.Schema(channel_fields),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    registry = er.async_get(hass)
    obsolete = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_internal_temperature"
    )
    if obsolete:
        registry.async_remove(obsolete)
    for platform, unique_id in (
        ("button", f"{entry.unique_id}_download_memory"),
        ("sensor", f"{entry.unique_id}_export"),
    ):
        obsolete = registry.async_get_entity_id(platform, DOMAIN, unique_id)
        if obsolete:
            registry.async_remove(obsolete)
    coordinator = UT325FCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
