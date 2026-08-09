# Hardware Compatibility Checks — Multi-Component Builds

## When to use this workflow

David is ordering 2-4 components from the same vendor (typically Pi Hut UK) and needs to know if they'll physically work together. This is a **lightweight inline check** — not the full multi-agent research pipeline. Do it yourself by reading product pages and cross-referencing specs.

## Common scenarios

- Pi accessory stack (HAT + display + microphone + speaker + NVMe)
- Audio input/output pairing (microphone array + amplified speaker)
- Display + touch interface choices (HDMI vs DSI vs SPI e-ink alternatives)
- Cable discovery (which cables aren't included in any box)

## Signals to start this workflow

- David sends multiple product URLs and asks "will these work together"
- David says "check if there's anything else I need" or "what am I missing"
- David asks for a better option for a specific part in a multi-component order

## Workflow

### 1. For each component, extract from the product page:

| Attribute | Example |
|-----------|---------|
| **Interface** | HDMI, USB-C, USB-A, GPIO/40-pin, SPI, I2S, 3.5mm jack, JST 2PH |
| **Power** | 5V via USB, 5V via GPIO, battery, external PSU pad |
| **Form factor** | HAT (GPIO top), HAT+ (with EEPROM), standalone USB device, breakout |
| **Connector type** | USB-C (5W PD), JST PH 2.0mm 2-pin, micro-HDMI, 3.5mm TRS |
| **Driver needed** | Built-in, driver-free, HAT EEPROM, manual config |
| **OEM companion parts** | "Mono Enclosed Speaker for ReSpeaker Lite" — buy this, not a generic |

Use `web_extract` on each product page (not just summary — go into spec tables and package contents).

### 2. Check for conflicts

**Physical stacking:**
- GPIO HATs compete for the 40-pin header. NVMe Base uses GPIO pass-through, so HATs can stack on top — but check physical clearance. A HAT that needs an EEPROM (HAT+) will work with NVMe Base's pass-through.
- HDMI displays use the micro-HDMI port. Pi 5 has two micro-HDMI — confirm you're using the right one (HDMI0 is the one nearest the USB-C power).
- USB-C devices compete for USB-A ports via adapters. The ReSpeaker Lite needs USB-A to USB-C, same for display touch input.
- Round displays (HDMI + USB touch) require TWO ports: HDMI video + USB touch data.

**Connector match between audio devices:**
- The ReSpeaker Lite has a **Speaker Connector** (label 11 on the board) — an amplified 5W output via a 2-pin JST connector.
- If buying a 3rd-party speaker (not the OEM Seeed one), check connector type: JST PH 2.0mm 2-pin is common. But OEM is safer — Seeed sells a companion speaker specifically for this board. Buy that one.
- If connector type is unclear from the page, check: "3.5mm headphone jack" is a line-level output (needs active speaker or separate amp). "Speaker connector" is amplified and needs a passive speaker.
- The ReSpeaker's 3.5mm jack outputs audio too — but it's line-level, not amplified. Use this only with powered speakers or headphones.

**Power budget:**
- Pi 5 needs a 27W (5V/5A) USB-C PSU. The official Pi 5 PSU delivers this.
- NVMe Base draws power from the Pi's GPIO (no additional PSU).
- ReSpeaker Lite: USB-powered from Pi's USB-A port (~100mA nominal).
- Round HDMI display: needs 5V/300mA via separate USB-C (touch data + power). Can be powered from Pi's USB-A or an external USB-C PSU.
- GPIO HATs (e-ink, etc.): draw power from Pi's GPIO (typically <50mA).
- Total: the Pi's 5V rail must supply the Pi itself (~3A under load) + NVMe (~0.5A) + ReSpeaker (~0.1A) + display USB (~0.3A) + any e-ink HAT (~0.05A) = within budget on a 5V/5A supply. But don't blindly assume — check peak current from each component spec.

### 3. Check for missing cables

Product pages often say "cable not included" or "not included in the box." Common omissions:

| Cable | From | To | Typical missing scenario |
|-------|------|----|--------------------------|
| micro-HDMI to HDMI | Pi 5 (micro-HDMI) | Round display (HDMI) | Pi Hut Waveshare display pages say not included |
| USB-A to USB-C | Pi 5 (USB-A) | ReSpeaker Lite / display touch | Neither device includes it (they assume USB-C to USB-C or you have one) |
| USB-C to USB-C | Display PSU | Display | If powering display separately |
| JST PH pigtail | ReSpeaker | 3rd-party speaker | Only if not using OEM Seeed speaker which has the mate |

**Cable shopping list format:** Deliver as a simple bullet list David can add to his cart. Each with a brief label: `1x micro-HDMI to HDMI (Pi 5 → display)`, `2x USB-A to USB-C (Pi → ReSpeaker, Pi → display touch)`.

### 4. Give a compatibility verdict

End with a clear status for each part:

| Part | Compatible | Notes |
|------|------------|-------|
| ReSpeaker Lite | ✅ | USB audio device, Pi 5 detects as sound card |
| Mono Speaker 3W 4Ω | ⚠️ | Connector may not mate — OEM Seeed speaker preferred |
| Round HDMI display | ✅ | HDMI + USB-touch, driver-free |

And a **recommended BOM** that reorders the items David originally listed, swapping in better-matched alternatives (e.g. OEM speaker instead of generic):

1. ReSpeaker Lite with XIAO ESP32S3
2. Mono Enclosed Speaker for ReSpeaker Lite (4Ω 5W) — Seeed OEM
3. 3.4" HDMI Round Touch Display
4. micro-HDMI to HDMI cable
5. USB-A to USB-C cable x2
6. *(existing parts: Pi 5, NVMe Base, 1TB SSD, Active Cooler)*

### 5. Consider alternatives on the same vendor's site

When David asks "is there a better option for X," check the vendor's full catalogue for that category before answering. E.g. for speakers: The Pi Hut sells a whole collection of speakers — scan the category page, identify the OEM companion part, and recommend that if it exists.

### Pitfalls

1. **Don't assume JST connectors are standardised.** JST PH (2.0mm pitch) and JST XH (2.5mm pitch) look similar but don't mate. Get the exact pinout from the OEM companion part if one exists.
2. **HDMI port numbering on Pi 5.** HDMI0 (nearest the USB-C power port) is the primary display. If the round display is the only HDMI device, either port works. But if adding a second HDMI display later, know which is which.
3. **USB port competition.** Pi 5 has 2 USB-A ports. You need: keyboard/mouse (if using as desktop) + ReSpeaker + display touch = 3 USB devices. Either use a USB hub, or power the display touch from a separate USB-C PSU (the display has its own USB-C input for power + touch data).
4. **e-ink HATs + NVMe Base.** The NVMe Base has a pass-through 40-pin GPIO header, so a HAT can stack on top. But check the HAT's physical height — some have tall caps or LEDs that might interfere with the NVMe Base's underside clearance.
5. **Refresh speed matters for notification displays.** Full-colour Spectra 6 e-ink takes ~19 seconds to refresh. Tri-colour/quad-colour e-ink with partial refresh updates in ~2-3 seconds. Choose based on use case: aesthetic always-on display vs notification ticker.
