"""Configuration flow for Airzone Enerface."""
import asyncio
import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, LOGIN_URL

_LOGGER = logging.getLogger(__name__)


class EnerfaceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Authenticate before storing an Airzone Cloud account."""

    VERSION = 2

    async def _validate_credentials(self, email: str, password: str) -> str | None:
        """Return a safe form error or None on successful authentication."""
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(
                LOGIN_URL,
                json={"email": email, "password": password},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                if response.status in (401, 403):
                    return "invalid_auth"
                if response.status >= 400:
                    _LOGGER.warning("Airzone credential validation failed (HTTP %s)", response.status)
                    return "cannot_connect"
                payload = await response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get("token"), str) or not payload["token"]:
                    return "invalid_response"
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return "cannot_connect"
        except (ValueError, TypeError):
            return "invalid_response"
        return None

    @staticmethod
    def _schema(default_email: str = "") -> vol.Schema:
        return vol.Schema({
            vol.Required(CONF_EMAIL, default=default_email): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_NAME, default="Airzone Enerface"): str,
        })

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            error = await self._validate_credentials(email, user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(email)
                self._abort_if_unique_id_configured()
                user_input[CONF_EMAIL] = email
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "Airzone Enerface"),
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(
                user_input.get(CONF_EMAIL, "") if user_input else ""
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Offer a way to replace credentials on an existing entry."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            error = await self._validate_credentials(email, user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(email)
                self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data_updates={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self._schema(
                user_input.get(CONF_EMAIL, "") if user_input
                else self._reauth_entry.data.get(CONF_EMAIL, "")
            ),
            errors=errors,
        )
