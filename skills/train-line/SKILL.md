---
name: train-line
description: Use for UK rail live departures, arrivals, disruption checks, and read-only journey links. Uses National Rail Darwin OpenLDBWS first and JourneyCheck as a read-only fallback.
version: 2.0.0
author: Araminta Milland-Wilde
license: MIT
ownership: collab
tags: [uk-rail, live-departures, journey-planning, journeycheck]
---

# Train Line

API-first UK rail information. All actions in this skill are read-only.

## Capabilities

1. Live departure and arrival boards through National Rail Darwin OpenLDBWS.
2. Calling-point filtering for services that stop at a destination.
3. National Rail journey planner link generation for a date and time.
4. Read-only SWR JourneyCheck links as a live-information fallback.

## Configuration

Copy `config.example.json` to the ignored `config.json` and replace the placeholder with an OpenLDBWS token:

```json
{
  "darwin_api_token": "YOUR_DARWIN_TOKEN_HERE"
}
```

Never commit `config.json`. The departures script validates configuration before it creates a SOAP client or makes a network request. A missing, blank, malformed, or placeholder token produces an immediate configuration error.

`config/stations.json` contains only generic public station aliases. Any three-letter CRS code can be supplied directly. Users may customise that file in their own deployment, but environment-specific aliases must not be committed to this public package.

## Live Boards

```bash
python3 scripts/departures.py WAT --rows 5
python3 scripts/departures.py WAT --arrivals --rows 5
python3 scripts/departures.py WAT --to CLJ --rows 5
```

The script uses the HTTPS OpenLDBWS WSDL and explicit request and operation timeouts. Output includes scheduled and expected times, platform, cancellation status, delay reasons, and National Rail disruption messages when available.

Darwin boards are for current live running information. They are not a future timetable service.

## Journey Links

```bash
python3 scripts/journey.py --from WAT --to CLJ
python3 scripts/journey.py --from WAT --to CLJ --date 2026-08-15 --time 09:00
python3 scripts/journey.py --from WAT --to CLJ --return --return-time 18:00
```

The script emits:

- a National Rail journey planner URL for the requested date and time
- an SWR JourneyCheck URL for read-only current live information
- equivalent return links when requested

JourneyCheck is a practical fallback for live SWR disruption and calling-point information. It does not replace a future timetable query and this skill does not submit forms or authenticate to it.

## Fallback Order

1. Run `departures.py` for live Darwin data.
2. If Darwin is unavailable or the token is not configured, generate links with `journey.py`.
3. Read the JourneyCheck URL for current SWR live information where applicable.
4. Use the National Rail link for the requested date and time.

Do not guess live service status when both live sources are unavailable.

## Dependencies

- Python 3.11 or newer
- `zeep` for `scripts/departures.py`
- network access to National Rail OpenLDBWS

`scripts/journey.py` uses only the Python standard library.

## Verification

```bash
python3 -m compileall -q scripts tests
python3 tests/test_train_line.py
python3 scripts/departures.py WAT
python3 scripts/journey.py --from WAT --to CLJ --date 2026-08-15 --time 09:00
```

The third command must fail quickly and clearly when `config.json` is absent. With a valid local token, it should return an authenticated board instead.
