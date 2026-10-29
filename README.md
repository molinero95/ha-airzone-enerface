# Airzone Enerface for Home Assistant

Experimental, unofficial Home Assistant integration for Airzone Cloud Enerface energy clamps. Not affiliated with Airzone.

> **Development status:** Local cloud authentication, installation discovery and live Enerface readings have been verified with a real account. Home Assistant device/entity discovery is still under testing. This is not yet a stable integration.

## Features

- Airzone Cloud email/password configuration with login validation
- Discover installations and subscribe to energy-clamp devices over Socket.IO
- Power (W), current (A) and voltage (V) sensors from `DEVICE_STATE`
- Automatic reconnection with exponential backoff and token refresh
- Safe HTTP status/stage diagnostics without exposing credentials or tokens
- Spanish and English configuration messages

## Installation through HACS

1. In HACS, add `https://github.com/molinero95/ha-airzone-enerface` as a **custom repository** of type **Integration**.
2. Install **Airzone Enerface** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Airzone Enerface**.
4. Enter your Airzone Cloud email and password.
5. Check the integration's devices and entities. If none appear, check Home Assistant logs for `custom_components.airzone_enerface`.

The integration stores account credentials in Home Assistant's config-entry storage. Protect backups and never share passwords, JWTs, refresh tokens, or full WebSocket URLs in logs/issues.

## Local diagnostics (no Home Assistant required)

The standalone diagnostics script is available on the `feat/local-diagnostics` branch and proposed in [PR #5](https://github.com/molinero95/ha-airzone-enerface/pull/5). Until that PR is merged, check out that branch first.

```bash
git fetch origin
git switch --track origin/feat/local-diagnostics
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/diagnose_airzone.py
```

The script prompts for credentials and checks login, installation listing, Socket.IO connectivity, and incoming Enerface measurements. It does not print tokens or passwords.

## Releases and tags

GitHub Actions workflow `.github/workflows/release.yml` runs tests and publishes a semantic-version tag and GitHub Release when a PR with a **new version in `manifest.json`** is merged into `main`. It never pushes commits to protected `main`. For a new release, update `custom_components/airzone_enerface/manifest.json` (for example, `0.1.1`) in the PR before merging. If that version's tag already exists, the workflow skips publication. GitHub Actions needs **Contents: write** permission to create tags and releases. Verify actual publication in [Releases](https://github.com/molinero95/ha-airzone-enerface/releases) and [Actions](https://github.com/molinero95/ha-airzone-enerface/actions).

## Development and tests

```bash
python3 -m compileall -q custom_components
python3 -m pip install pytest
python3 -m pytest -q tests
```

GitHub Actions also runs these basic checks on pushes and pull requests.

## Known limitations

- Home Assistant sensor discovery and live operation are not yet verified end to end.
- Daily/hourly kWh, cumulative energy and Home Assistant Energy dashboard support are not yet implemented.
- Installation-list pagination is not implemented (currently requests 9 installations).
- Credential reauthentication flow exists, but automatic prompting on authentication failure is not yet wired into the connection loop.
- Socket.IO `ready` handshake alignment is proposed in [PR #6](https://github.com/molinero95/ha-airzone-enerface/pull/6).

## Roadmap

1. Verify Home Assistant entity discovery and WebSocket subscription.
2. Add robust reauthentication and recovery from expired sessions.
3. Implement cumulative energy and historical consumption.
4. Expand automated integration tests and release checks.

## License

MIT intended; LICENSE file pending.
