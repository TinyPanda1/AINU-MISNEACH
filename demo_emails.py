"""
demo_emails.py - realistic supplier delay notices.

Every part number below is a real, in-production MPN, so the Nexar lookups
during a demo return genuine stock, pricing, lead times and alternates. The
emails are written the way suppliers actually write them: buried part numbers,
a conversational tone, and the bad news halfway down the third paragraph.
"""

MERIDIAN = """From: Rachel Ortiz <rortiz@meridian-components.com>
To: founder@atlasrobotics.io
Subject: RE: PO 4471 - schedule change on the driver line

Stu,

Bad news on PO 4471. Our allocation from TI shifted again and the
DRV8825PWPR you have on order (qty 500) is now quoting a 22 week factory
lead time. Best case we ship earlier, but I would not build a schedule
around it.

The TPS54331DR on the same PO is unaffected and ships Friday as planned.

I know this is the second slip on this line. If you want to dual-source the
driver I can try to quote alternates, but our stock position is thin across
the board right now and I can't promise anything this quarter.

Rachel Ortiz
Meridian Components | 312-555-0148
"""

NORDIC = """From: supply@nordic-electronics-dist.com
To: purchasing@atlasrobotics.io
Subject: Allocation notice - order 88213

This is an automated allocation notice. Do not reply to this message.

  Part:                  STM32F405RGT6
  Quantity ordered:      1,200 pcs
  Original ship date:    2026-10-02
  Revised ship date:     2027-01-15
  Reason:                manufacturer allocation

Your order remains in the queue at its original position. No action is
required on your part.

Nordic Electronics Distribution
"""

MARCUS = """stu - heads up, the encoder line is stalled

AS5600-ASOM qty 800 just got pushed to 16 weeks, supplier is blaming a
wafer shortage upstream. thats past the pilot build date.

also heads up the L298N we use on the test rigs is going EOL at our main
distributor, they want us off it by end of year.

need a plan before friday

- Marcus
"""

DEMO_EMAILS = [
    {
        "id": "meridian",
        "label": "Meridian Components - stepper driver allocation",
        "sender": "Rachel Ortiz, Meridian Components",
        "blurb": "Two MPNs buried in prose, only one of which is actually delayed.",
        "body": MERIDIAN,
        "expect": "DRV8825PWPR delayed 22 weeks, qty 500. TPS54331DR is fine.",
    },
    {
        "id": "nordic",
        "label": "Nordic Electronics - MCU allocation notice",
        "sender": "Automated allocation system",
        "blurb": "Machine-generated notice quoting both the original and revised dates.",
        "body": NORDIC,
        "expect": "STM32F405RGT6, qty 1,200, slipped to 2027-01-15.",
    },
    {
        "id": "marcus",
        "label": "Internal note - encoder line stalled",
        "sender": "Marcus (operations)",
        "blurb": "Unstructured internal message, lowercase, two parts, one EOL warning.",
        "body": MARCUS,
        "expect": "AS5600-ASOM delayed 16 weeks, qty 800. L298N going EOL.",
    },
]

EMAIL_INDEX = {e["id"]: e for e in DEMO_EMAILS}
