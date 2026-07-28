# Polaris Asset Inventory — Speaker Outline (2–3 min)

Walkthroughs are definitive. The supported event path contains 38 canonical
recoveries across the A0–A16 plus range-DNS topology in 5 objective groups.

## 1. Public / internet-facing
- Corporate website (A0), authoritative DNS, intranet wiki + webmail (A3).

## 2. Corporate IT — Windows shop
- Active Directory domain controller (A2, Server 2022 — LDAP, Kerberos, DCSync-able).
- SMB file share (A4, Public / HR / IT / Procurement).
- Mail server (A1, Dovecot / Roundcube).

## 3. Engineering / DevOps
- Gitea source repos (A7) for the product line — navigation, assembly, weapons-integration, manufacturing-orchestrator. Deleted-commit history intact.
- Engineering workstation (A6) — Jenkins CI, simulation archives, design files.

## 4. Research / lab data
- PostgreSQL research database (A8) with compartmented schemas and SECURITY DEFINER functions.
- Analyst workstation (A16) — SSH pivot into the lab net, `.pgpass`, SSH keys.

## 5. OT / ICS — the bunker
- Splice landing box (A9) as the IT→OT jump.
- Three authored Modbus/TCP controller services: tail (A10), leg (A11), arms
  (A12) — stateful registers, coils, device IDs, and serials for the fictional
  NORTHSTORM platform.
- "Brain" master controller (A13) on a custom binary TCP protocol with SHA256 XOR challenge-response.
- SCADA HMI gateway (A5) — web HMI on 8080, Modbus on 502, fuel / cooling / temperature logic.

## 6. Attacker + pivot surface
- Kali attack box (A14) — curl, nmap, smbclient, ldapsearch, Impacket, pymodbus, john / hashcat, psql, git, gpg.
- Ops engineer workstation (A15) — the sanctioned OT bridge, SSH pivot to SCADA.

## Arc to call out
OSINT → front-office AD / mail / SMB → lab via Gitea + research DB → bunker
OT controllers → master override. The enterprise and Windows AD services are
real range services. The fictional NORTHSTORM HMI and Modbus controllers are
authored event simulations, not vendor-supported hardware twins; they support
the event path but do not establish golden authenticity.
