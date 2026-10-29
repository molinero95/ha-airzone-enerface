# Airzone Enerface for Home Assistant

**Experimental, unofficial integration. Not affiliated with Airzone.**

Connect an Airzone Enerface energy clamp to Home Assistant using the Airzone Cloud Socket.IO stream. The implementation is an early prototype based on observed web-app traffic; **it has not yet been validated against a running Home Assistant instance**.

## Current scope

- Configuration flow for a device ID and a temporary access JWT
- Socket.IO `DEVICE_STATE` event listener, filtered by device ID
- Live power (W), current (A), and voltage (V) sensors
- Reconnection attempts and device availability tracking

## Not implemented yet

- Username/password login and secure refresh-token rotation
- Daily/hourly energy via `/api/v1/bg/energy`
- Energy dashboard compatible cumulative kWh sensor
- Verified Socket.IO handshake and authentication parameters
- Automated tests and release packaging

## Experimental manual installation

Copy `custom_components/airzone_enerface` to the Home Assistant `config/custom_components/` directory, restart Home Assistant, then add **Airzone Enerface** under Settings → Devices & services. Enter the energy clamp's device ID and a valid short-lived access token. **Do not paste credentials into GitHub issues.**

**Known limitation:** The browser WebSocket URL uses a `jwt` query parameter, but the prototype currently sends a Bearer authorization header. This authentication path has not been confirmed to work. Tokens expire, and refresh is not implemented. Treat this as source code for development, not a stable installation.

## Security

Never commit access tokens, refresh tokens, passwords, installation IDs, personal data, or captured full WebSocket URLs. If you have exposed an active JWT, revoke it if possible.

## Roadmap

1. Validate Socket.IO connection and JWT authentication without leaking tokens in logs.
2. Discover and implement refresh-token endpoint.
3. Add daily/hourly energy API and energy dashboard support.
4. Add tests, translations, diagnostics, and HACS release workflow.

## License

MIT (see LICENSE).
