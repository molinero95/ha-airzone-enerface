"""Configuration flow for Airzone Enerface."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD

CONF_INSTALLATION_ID = "installation_id"

class EnerfaceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].strip().lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, "Airzone Enerface"),
                data=user_input,
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_INSTALLATION_ID): str,
                vol.Optional(CONF_NAME, default="Airzone Enerface"): str,
            }),
        )
