from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN


class UT325FConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": discovery_info.name}
        self._discovery = discovery_info
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery.name,
                data={"address": self._discovery.address},
            )
        return self.async_show_form(step_id="confirm")

    async def async_step_user(self, user_input=None) -> FlowResult:
        devices = {
            info.address: info.name
            for info in async_discovered_service_info(self.hass, connectable=True)
            if (info.name or "").upper().startswith("UT325F")
        }
        if not devices:
            return self.async_abort(reason="not_found")
        if user_input is not None:
            address = user_input["address"]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=devices[address], data={"address": address}
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("address"): vol.In(devices)}),
        )
