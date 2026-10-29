# Airzone Enerface for Home Assistant

Experimental, unofficial integration. Not affiliated with Airzone.

## Prototype capabilities

- Config flow for Airzone Cloud email, password, and energy clamp device ID
- Automatic login through the observed Airzone Cloud endpoint
- Socket.IO connection with JWT query authentication
- Power (W), current (A), and voltage (V) from `DEVICE_STATE`
- Re-login after disconnection

## Installation (development only)

Copy `custom_components/airzone_enerface` to Home Assistant's `config/custom_components/`, restart, and add **Airzone Enerface** from Settings → Devices & services.

The integration has **not been tested with a live Home Assistant installation**. The Socket.IO handshake and authentication still require validation. Credentials are stored in Home Assistant's config-entry storage, not in the repository. Protect your Home Assistant backups. Do not share passwords, JWTs, refresh tokens, or full WebSocket URLs in issues.

## Known limitations

- No refresh-token endpoint has been verified; the prototype logs in again after disconnecting.
- A server that keeps the WebSocket connected beyond JWT expiry may require proactive reconnect logic.
- Daily/hourly kWh and Energy dashboard support are not yet implemented.
- No automated test suite yet.
- Repeated authentication failures currently retry every 30 seconds; this needs backoff before general release.
- No public HACS release yet.

## Roadmap

1. Validate authentication and Socket.IO handshake.
2. Add credential validation and exponential retry backoff.
3. Identify and implement refresh-token flow.
4. Add daily energy API and cumulative kWh sensor.
5. Add tests, translations, diagnostics, and release automation.

## License

MIT (license file pending).
