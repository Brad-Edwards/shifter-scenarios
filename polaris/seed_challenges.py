# POLARIS -> CTF challenge seed (38 flags 1-38; 39-42 excluded, assets a17/a18 not deployed).
# Flag values verified against baked boxes 2026-07-21. EVENT_ID is per-event; update before reuse.
# Run in the portal Django shell (Active events are not content-modifiable, so this uses
# direct-ORM create with hash_flag rather than create_challenge()). Idempotent by challenge name.

from uuid import UUID
from ctf.models import CTFEvent, CTFChallenge
from ctf.services.challenge._flag_verify import hash_flag

EVENT_ID = UUID("3829fe6c-c5e7-4dd5-95c0-f05ad4d305e3")
ev = CTFEvent.objects.get(pk=EVENT_ID)

# (num, name, difficulty, points, flag, group) — verified against baked boxes
FLAGS = [
    (1, "Company Info", "easy", 50, "FLAG{8f3a2c1e9b7d4056}", "osint"),
    (2, "Employee Directory", "easy", 50, "FLAG{d4e7b1f283a6c950}", "osint"),
    (3, "Tech Stack Revealed", "easy", 50, "FLAG{a1c9e3f7054b82d6}", "osint"),
    (4, "Client Contracts", "easy", 50, "FLAG{72b5e0d8f1a34c69}", "osint"),
    (5, "DNS Reconnaissance", "easy", 50, "FLAG{5e9c2a0f73b148d6}", "osint"),
    (6, "Follow the Money", "medium", 100, "FLAG{c6f8d2b3e91a4507}", "osint"),
    (7, "Configuration Leak", "easy", 50, "FLAG{4f2e8b7a1c6d9035}", "front"),
    (8, "Project Hints", "easy", 50, "FLAG{3b7e9a2d1c8f4063}", "front"),
    (9, "Terminated Engineer", "easy", 50, "FLAG{7a1b3d9e2c8f0546}", "front"),
    (10, "Password Reuse", "easy", 50, "FLAG{e5d1f8c2a7b03946}", "front"),
    (11, "Mundane File Share", "easy", 50, "FLAG{0e6f9c2d4a8b7135}", "front"),
    (12, "The Project", "easy", 50, "FLAG{d8a3c5e9f1b07264}", "front"),
    (13, "Procurement Trail", "medium", 100, "FLAG{8c5a0d3f7e1b2964}", "front"),
    (14, "Hidden Group", "medium", 100, "FLAG{2f8b4a6c1d9e7053}", "front"),
    (15, "Lateral Movement", "medium", 100, "FLAG{9a4c7e2f58d0b163}", "front"),
    (16, "Unreliable Guard", "medium", 100, "FLAG{b3d7e1f0c8a24596}", "front"),
    (17, "Domain Admin", "hard", 200, "FLAG{6c0a9d4e7f2b8135}", "front"),
    (37, "On Call", "hard", 200, "FLAG{5c3e7a9f1b8d4602}", "front"),
    (18, "Control Room", "hard", 200, "FLAG{1d4e7b0a3c9f8265}", "front"),
    (19, "Lights Out", "expert", 300, "FLAG{a7f2c8d0e5b34169}", "front"),
    (38, "The Analyst's Desk", "medium", 100, "FLAG{8b2d4f1a0c5e7396}", "lab"),
    (20, "Old Defaults", "easy", 50, "FLAG{5b8e1d3a7c0f9246}", "lab"),
    (21, "Compartment A", "easy", 50, "FLAG{4b9e2a7d0c8f1365}", "lab"),
    (22, "Heavy Delivery", "easy", 50, "FLAG{e2a9c4f7d8b01536}", "lab"),
    (23, "MIDNIGHT-7", "medium", 100, "FLAG{0c7d8a2e5f1b3946}", "lab"),
    (24, "What Git Remembers", "medium", 100, "FLAG{8a0e3c7f2d5b1946}", "lab"),
    (25, "After Hours", "medium", 100, "FLAG{3f6a9d1e7c4b0258}", "lab"),
    (26, "Balance Point", "medium", 100, "FLAG{7e2b0c5d9a4f8163}", "lab"),
    (27, "Compartment B", "medium", 100, "FLAG{6d1a8f3c7e0b4952}", "lab"),
    (28, "What's Built", "hard", 200, "FLAG{a3f7d9e1c0b52846}", "lab"),
    (29, "What Was Erased", "hard", 200, "FLAG{1f9b4e7c0a3d8265}", "lab"),
    (30, "Full Run", "expert", 300, "FLAG{d4c8f0a2e6b71935}", "lab"),
    (31, "Underground Signals", "medium", 100, "FLAG{2e8c0a5d7f3b1946}", "bunker"),
    (32, "First Motion", "hard", 200, "FLAG{9b3e7c1d0f5a2846}", "bunker"),
    (33, "Walking Pattern", "hard", 200, "FLAG{c7a1e3f9d0b52864}", "bunker"),
    (34, "Response Window", "hard", 200, "FLAG{f0d8b2e6a4c71935}", "bunker"),
    (35, "Control Channel", "expert", 300, "FLAG{8d2f5a0e7c9b3146}", "bunker"),
    (36, "Full Override", "expert", 300, "FLAG{0b7e3d9a1f6c4258}", "bunker"),
]

GROUPS = {
    "osint": ("osint", "OSINT — Boreas Systems public website (http://172.20.0.10). No authentication required."),
    "front": ("network", "Front Office — the Boreas corporate network and the BOREAS.LOCAL Active Directory domain (dc01.boreas.local). Pivot from your Kali workstation."),
    "lab": ("misc", "Research Lab — Boreas internal research and analyst systems."),
    "bunker": ("hardware", "The Bunker — Boreas OT / industrial control systems (SCADA, PLCs, robotics)."),
}

existing = set(CTFChallenge.objects.filter(event_id=EVENT_ID).values_list("name", flat=True))
created = 0
skipped = 0
errors = []
for (num, name, diff, pts, flag, grp) in FLAGS:
    if name in existing:
        skipped += 1
        continue
    cat, blurb = GROUPS[grp]
    desc = (
        blurb
        + "\n\nObjective: " + name + " (" + diff + ", " + str(pts) + " pts)."
        + "\n\nRecover the flag (format FLAG{...}) and submit it here."
    )
    try:
        CTFChallenge.objects.create(
            event=ev, name=name, description=desc, category=cat, points=pts,
            difficulty=diff, flag_hash=hash_flag(flag), flag_format="FLAG{...}",
            visibility="visible", order=num,
        )
        created += 1
    except Exception as e:
        errors.append((name, repr(e)[:160]))

print("SEED_CREATED", created, "SKIPPED", skipped, "ERRORS", len(errors))
for n, e in errors:
    print("SEED_ERR", n, e)
print("SEED_TOTAL_CHALLENGES", CTFChallenge.objects.filter(event_id=EVENT_ID).count())
