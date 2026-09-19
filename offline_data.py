"""
offline_data.py - demo safety net.

A snapshot of Nexar-shaped part payloads for the parts used in the demo emails.
If the live API is unreachable, rate limited, out of quota or simply slow, the
app falls back to these so a demo never dies on stage.

These are REPRESENTATIVE FIGURES, not live data. Everything here is shaped
exactly like a supMultiMatch part node so the rest of the pipeline cannot tell
the difference - but the UI always labels which mode produced what you are
looking at, because presenting these numbers as live distributor data would be
a lie to whoever is watching.
"""

SNAPSHOT_LABEL = "offline snapshot, representative figures"


def _part(mpn, manufacturer, description, category, sellers, similar=(), median=None):
    """Build a part node in Nexar's supMultiMatch shape."""
    total = sum(s[1] for s in sellers)
    return {
        "mpn": mpn,
        "name": description,
        "shortDescription": description,
        "octopartUrl": "",
        "totalAvail": total,
        "manufacturer": {"name": manufacturer},
        "category": {"name": category},
        "bestDatasheet": {"url": ""},
        "medianPrice1000": (
            {"price": median, "currency": "USD",
             "convertedPrice": median, "convertedCurrency": "USD"}
            if median is not None else None
        ),
        "specs": [],
        "similarParts": [
            {"mpn": m, "name": n, "manufacturer": {"name": mfr}, "totalAvail": avail}
            for m, n, mfr, avail in similar
        ],
        "sellers": [
            {
                "company": {"name": company},
                "offers": [{
                    "inventoryLevel": stock,
                    "factoryLeadDays": lead,
                    "moq": moq,
                    "packaging": "Tape & Reel",
                    "clickUrl": "",
                    "prices": [
                        {"quantity": q, "price": p, "convertedPrice": p,
                         "currency": "USD", "convertedCurrency": "USD"}
                        for q, p in breaks
                    ],
                }],
            }
            for company, stock, lead, moq, breaks in sellers
        ],
    }


OFFLINE_PARTS = {
    # ---- Meridian email ---------------------------------------------------
    "DRV8825PWPR": _part(
        "DRV8825PWPR", "Texas Instruments",
        "Stepper Motor Driver, 8.2V-45V, HTSSOP-28",
        "Motor / Motion / Ignition Controllers & Drivers",
        sellers=[
            ("Digi-Key", 8214, 84, 1, [(1, 5.82), (100, 4.31), (1000, 3.55)]),
            ("Mouser", 3190, 77, 1, [(1, 5.94), (100, 4.44), (1000, 3.61)]),
            ("Arrow Electronics", 0, 154, 1500, [(1500, 3.10)]),
            ("LCSC", 15400, 90, 10, [(10, 3.48), (100, 2.95), (1000, 2.71)]),
        ],
        similar=[
            ("DRV8824PWPR", "Stepper Motor Driver 1.6A", "Texas Instruments", 4120),
            ("A4988SETTR-T", "Stepper Motor Driver 2A", "Allegro MicroSystems", 9860),
            ("TMC2209-LA-T", "Stepper Driver, StealthChop", "Analog Devices (Trinamic)", 2410),
            ("DRV8834PWPR", "Stepper Motor Driver, Low Voltage", "Texas Instruments", 1875),
        ],
        median=3.91,
    ),
    "TPS54331DR": _part(
        "TPS54331DR", "Texas Instruments",
        "Step-Down Converter 3A 28V, SOIC-8",
        "Voltage Regulators - DC-DC Switching Regulators",
        sellers=[
            ("Digi-Key", 31480, 56, 1, [(1, 1.71), (100, 1.09), (1000, 0.92)]),
            ("Mouser", 18220, 63, 1, [(1, 1.76), (100, 1.13), (1000, 0.95)]),
            ("Newark", 4400, 70, 1, [(1, 1.88), (100, 1.21)]),
        ],
        similar=[
            ("TPS54332DDAR", "Step-Down Converter 3.5A", "Texas Instruments", 12400),
            ("LM2596S-5.0/NOPB", "Step-Down Regulator 3A", "Texas Instruments", 8800),
        ],
        median=0.98,
    ),

    # ---- Nordic email -----------------------------------------------------
    "STM32F405RGT6": _part(
        "STM32F405RGT6", "STMicroelectronics",
        "ARM Cortex-M4 MCU 1MB Flash 168MHz, LQFP-64",
        "Microcontrollers (MCU/MPU/SOC)",
        sellers=[
            ("Digi-Key", 1240, 168, 1, [(1, 13.42), (100, 11.08), (1000, 9.87)]),
            ("Mouser", 860, 175, 1, [(1, 13.75), (100, 11.30)]),
            ("Arrow Electronics", 0, 196, 1000, [(1000, 9.44)]),
            ("Avnet", 2100, 182, 1, [(1, 13.10), (500, 10.65)]),
        ],
        similar=[
            ("STM32F405RGT6TR", "Cortex-M4 MCU, Tape & Reel", "STMicroelectronics", 3400),
            ("STM32F407VGT6", "Cortex-M4 MCU 1MB, LQFP-100", "STMicroelectronics", 5620),
            ("STM32F427VIT6", "Cortex-M4 MCU 2MB, LQFP-100", "STMicroelectronics", 1980),
            ("STM32F446RET6", "Cortex-M4 MCU 512KB, LQFP-64", "STMicroelectronics", 7310),
        ],
        median=10.24,
    ),

    # ---- Marcus email -----------------------------------------------------
    "AS5600-ASOM": _part(
        "AS5600-ASOM", "ams-OSRAM",
        "12-bit Magnetic Rotary Position Sensor, SOIC-8",
        "Magnetic Sensors - Position",
        sellers=[
            ("Digi-Key", 940, 112, 1, [(1, 3.55), (100, 2.88), (1000, 2.41)]),
            ("Mouser", 1680, 105, 1, [(1, 3.61), (100, 2.94)]),
            ("LCSC", 6200, 98, 10, [(10, 2.35), (100, 2.02)]),
        ],
        similar=[
            ("AS5601-ASOM", "12-bit Magnetic Encoder", "ams-OSRAM", 2240),
            ("AS5048A-HTSP", "14-bit Magnetic Rotary Encoder", "ams-OSRAM", 810),
            ("MT6701CT-STD", "14-bit Magnetic Rotary Encoder", "MagnTek", 4900),
        ],
        median=2.63,
    ),
    "L298N": _part(
        "L298N", "STMicroelectronics",
        "Dual Full-Bridge Motor Driver, Multiwatt-15",
        "Motor / Motion / Ignition Controllers & Drivers",
        sellers=[
            ("Digi-Key", 0, 0, 1, [(1, 6.12)]),
            ("Mouser", 310, 224, 1, [(1, 6.44), (100, 5.31)]),
            ("Win Source", 1450, 140, 10, [(10, 4.88)]),
        ],
        similar=[
            ("L298P", "Dual Full-Bridge Driver, PowerSO-20", "STMicroelectronics", 640),
            ("TB6612FNG,C,8,EL", "Dual DC Motor Driver 1.2A", "Toshiba", 8800),
            ("DRV8871DDAR", "Brushed DC Motor Driver 3.6A", "Texas Instruments", 11200),
        ],
        median=5.40,
    ),

    # ---- G4 family, for pasted emails outside the scripted demos -----------
    "STM32G474RET6": _part(
        "STM32G474RET6", "STMicroelectronics",
        "ARM Cortex-M4 MCU 512KB Flash 170MHz, LQFP-64",
        "Microcontrollers (MCU/MPU/SOC)",
        sellers=[
            ("Digi-Key", 2180, 140, 1, [(1, 8.54), (100, 7.21), (1000, 6.44)]),
            ("Mouser", 1460, 147, 1, [(1, 8.70), (100, 7.36)]),
            ("Arrow Electronics", 0, 182, 1000, [(1000, 6.18)]),
            ("Avnet", 3050, 154, 1, [(1, 8.32), (500, 6.95)]),
        ],
        similar=[
            ("STM32G474VET6", "Cortex-M4 MCU 512KB, LQFP-100", "STMicroelectronics", 1740),
            ("STM32G473RET6", "Cortex-M4 MCU 512KB, LQFP-64", "STMicroelectronics", 2960),
            ("STM32G474CET6", "Cortex-M4 MCU 512KB, LQFP-48", "STMicroelectronics", 4310),
            ("STM32G431RBT6", "Cortex-M4 MCU 128KB, LQFP-64", "STMicroelectronics", 8620),
        ],
        median=6.88,
    ),
    "STM32G474VET6": _part(
        "STM32G474VET6", "STMicroelectronics", "Cortex-M4 MCU 512KB Flash 170MHz, LQFP-100",
        "Microcontrollers (MCU/MPU/SOC)",
        sellers=[("Digi-Key", 1740, 154, 1, [(1, 9.24), (100, 7.88), (1000, 7.02)]),
                 ("Mouser", 980, 161, 1, [(1, 9.41), (100, 8.04)])],
        median=7.46,
    ),
    "STM32G473RET6": _part(
        "STM32G473RET6", "STMicroelectronics", "Cortex-M4 MCU 512KB Flash 170MHz, LQFP-64",
        "Microcontrollers (MCU/MPU/SOC)",
        sellers=[("Digi-Key", 2960, 126, 1, [(1, 8.11), (100, 6.84), (1000, 6.09)]),
                 ("Avnet", 1520, 133, 1, [(1, 7.95), (500, 6.60)])],
        median=6.52,
    ),
    "STM32G474CET6": _part(
        "STM32G474CET6", "STMicroelectronics", "Cortex-M4 MCU 512KB Flash 170MHz, LQFP-48",
        "Microcontrollers (MCU/MPU/SOC)",
        sellers=[("Digi-Key", 4310, 119, 1, [(1, 8.05), (100, 6.72), (1000, 5.94)]),
                 ("Mouser", 2240, 126, 1, [(1, 8.18), (100, 6.88)]),
                 ("LCSC", 6800, 112, 10, [(10, 6.41), (100, 5.70)])],
        median=6.20,
    ),
    "STM32G431RBT6": _part(
        "STM32G431RBT6", "STMicroelectronics", "Cortex-M4 MCU 128KB Flash 170MHz, LQFP-64",
        "Microcontrollers (MCU/MPU/SOC)",
        sellers=[("Digi-Key", 8620, 84, 1, [(1, 4.61), (100, 3.74), (1000, 3.28)]),
                 ("Mouser", 5140, 91, 1, [(1, 4.72), (100, 3.85)]),
                 ("LCSC", 11300, 77, 10, [(10, 3.52), (100, 3.01)])],
        median=3.44,
    ),

    # ---- alternates, so the second lookup also survives offline ------------
    "DRV8824PWPR": _part(
        "DRV8824PWPR", "Texas Instruments", "Stepper Motor Driver 1.6A, HTSSOP-28",
        "Motor / Motion / Ignition Controllers & Drivers",
        sellers=[("Digi-Key", 4120, 77, 1, [(1, 5.44), (100, 4.05), (1000, 3.32)]),
                 ("Mouser", 2260, 84, 1, [(1, 5.61), (100, 4.18)])],
        median=3.64,
    ),
    "A4988SETTR-T": _part(
        "A4988SETTR-T", "Allegro MicroSystems", "Stepper Motor Driver 2A, TSSOP-28",
        "Motor / Motion / Ignition Controllers & Drivers",
        sellers=[("Digi-Key", 9860, 63, 1, [(1, 4.02), (100, 2.74), (1000, 2.18)]),
                 ("LCSC", 21000, 70, 10, [(10, 2.44), (100, 1.96)])],
        median=2.31,
    ),
    "TMC2209-LA-T": _part(
        "TMC2209-LA-T", "Analog Devices (Trinamic)", "Stepper Driver StealthChop2, QFN-28",
        "Motor / Motion / Ignition Controllers & Drivers",
        sellers=[("Digi-Key", 2410, 91, 1, [(1, 7.28), (100, 6.15), (1000, 5.42)]),
                 ("Mouser", 1180, 98, 1, [(1, 7.44), (100, 6.31)])],
        median=5.88,
    ),
    "DRV8834PWPR": _part(
        "DRV8834PWPR", "Texas Instruments", "Stepper Motor Driver Low Voltage, HTSSOP-24",
        "Motor / Motion / Ignition Controllers & Drivers",
        sellers=[("Digi-Key", 1875, 84, 1, [(1, 5.10), (100, 3.88), (1000, 3.21)])],
        median=3.45,
    ),
    "STM32F405RGT6TR": _part(
        "STM32F405RGT6TR", "STMicroelectronics", "Cortex-M4 MCU 1MB, LQFP-64, Tape & Reel",
        "Microcontrollers (MCU/MPU/SOC)",
        sellers=[("Digi-Key", 3400, 154, 1, [(1, 13.42), (1000, 9.79)]),
                 ("Avnet", 1900, 161, 1, [(1, 13.05), (500, 10.40)])],
        median=10.11,
    ),
    "STM32F407VGT6": _part(
        "STM32F407VGT6", "STMicroelectronics", "Cortex-M4 MCU 1MB Flash, LQFP-100",
        "Microcontrollers (MCU/MPU/SOC)",
        sellers=[("Digi-Key", 5620, 112, 1, [(1, 14.88), (100, 12.40), (1000, 11.02)]),
                 ("Mouser", 3310, 119, 1, [(1, 15.10), (100, 12.66)])],
        median=11.44,
    ),
    "STM32F427VIT6": _part(
        "STM32F427VIT6", "STMicroelectronics", "Cortex-M4 MCU 2MB Flash, LQFP-100",
        "Microcontrollers (MCU/MPU/SOC)",
        sellers=[("Digi-Key", 1980, 126, 1, [(1, 18.22), (100, 15.61)])],
        median=14.90,
    ),
    "STM32F446RET6": _part(
        "STM32F446RET6", "STMicroelectronics", "Cortex-M4 MCU 512KB Flash, LQFP-64",
        "Microcontrollers (MCU/MPU/SOC)",
        sellers=[("Digi-Key", 7310, 84, 1, [(1, 9.88), (100, 8.02), (1000, 7.11)]),
                 ("Mouser", 4120, 91, 1, [(1, 10.04), (100, 8.20)])],
        median=7.40,
    ),
    "AS5601-ASOM": _part(
        "AS5601-ASOM", "ams-OSRAM", "12-bit Magnetic Encoder with PWM, SOIC-8",
        "Magnetic Sensors - Position",
        sellers=[("Digi-Key", 2240, 84, 1, [(1, 3.31), (100, 2.66), (1000, 2.24)])],
        median=2.42,
    ),
    "AS5048A-HTSP": _part(
        "AS5048A-HTSP", "ams-OSRAM", "14-bit Magnetic Rotary Encoder, TSSOP-14",
        "Magnetic Sensors - Position",
        sellers=[("Digi-Key", 810, 126, 1, [(1, 9.44), (100, 8.10)]),
                 ("Mouser", 460, 133, 1, [(1, 9.61), (100, 8.28)])],
        median=7.95,
    ),
    "MT6701CT-STD": _part(
        "MT6701CT-STD", "MagnTek", "14-bit Magnetic Rotary Encoder, SOP-8",
        "Magnetic Sensors - Position",
        sellers=[("LCSC", 4900, 49, 10, [(10, 1.12), (100, 0.94), (1000, 0.81)])],
        median=0.92,
    ),
    "L298P": _part(
        "L298P", "STMicroelectronics", "Dual Full-Bridge Driver, PowerSO-20",
        "Motor / Motion / Ignition Controllers & Drivers",
        sellers=[("Mouser", 640, 196, 1, [(1, 6.88), (100, 5.74)])],
        median=5.82,
    ),
    "TB6612FNG,C,8,EL": _part(
        "TB6612FNG,C,8,EL", "Toshiba", "Dual DC Motor Driver 1.2A, SSOP-24",
        "Motor / Motion / Ignition Controllers & Drivers",
        sellers=[("Digi-Key", 8800, 63, 1, [(1, 2.44), (100, 1.88), (1000, 1.52)]),
                 ("LCSC", 14200, 56, 10, [(10, 1.61), (100, 1.34)])],
        median=1.58,
    ),
    "DRV8871DDAR": _part(
        "DRV8871DDAR", "Texas Instruments", "Brushed DC Motor Driver 3.6A, SOIC-8",
        "Motor / Motion / Ignition Controllers & Drivers",
        sellers=[("Digi-Key", 11200, 49, 1, [(1, 2.88), (100, 2.21), (1000, 1.84)]),
                 ("Mouser", 6400, 56, 1, [(1, 2.95), (100, 2.28)])],
        median=1.91,
    ),
    "TPS54332DDAR": _part(
        "TPS54332DDAR", "Texas Instruments", "Step-Down Converter 3.5A, SO PowerPAD-8",
        "Voltage Regulators - DC-DC Switching Regulators",
        sellers=[("Digi-Key", 12400, 56, 1, [(1, 1.94), (100, 1.31), (1000, 1.08)])],
        median=1.14,
    ),
    "LM2596S-5.0/NOPB": _part(
        "LM2596S-5.0/NOPB", "Texas Instruments", "Step-Down Regulator 3A 5V, TO-263-5",
        "Voltage Regulators - DC-DC Switching Regulators",
        sellers=[("Digi-Key", 8800, 42, 1, [(1, 4.31), (100, 3.44), (1000, 2.98)]),
                 ("Mouser", 5200, 49, 1, [(1, 4.42), (100, 3.55)])],
        median=3.10,
    ),
}


def offline_match(mpns):
    """Same contract as NexarClient.match_mpns, served from the snapshot."""
    resolved = {}
    for mpn in mpns or []:
        part = OFFLINE_PARTS.get(mpn.upper()) or OFFLINE_PARTS.get(mpn)
        if part:
            resolved[mpn] = part
    return resolved


def offline_search(query, limit=5):
    """Same contract as NexarClient.search_parts, served from the snapshot."""
    needle = (query or "").strip().lower()
    if not needle:
        return []

    scored = []
    for mpn, part in OFFLINE_PARTS.items():
        haystack = " ".join([
            mpn,
            part.get("name") or "",
            (part.get("manufacturer") or {}).get("name") or "",
            (part.get("category") or {}).get("name") or "",
        ]).lower()
        if needle not in haystack:
            continue
        # exact MPN first, then MPN prefix, then anything matching the text
        if mpn.lower() == needle:
            rank = 0
        elif mpn.lower().startswith(needle):
            rank = 1
        elif needle in mpn.lower():
            rank = 2
        else:
            rank = 3
        scored.append((rank, mpn, part))

    scored.sort(key=lambda row: (row[0], row[1]))
    return [part for _, _, part in scored[:limit]]
