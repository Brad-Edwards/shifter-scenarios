#!/usr/bin/env python3
"""Generate the reviewed ARWC design modules without materializing the range.

The script emits private deterministic service-loader contracts, native RAE
runtime/application declarations, ordinary integration relationships, and
synchronized operation/card contracts. It does not build any service, binary,
image, process simulator, repository, or participant environment.
"""
from __future__ import annotations

from collections import defaultdict
from functools import cache
from pathlib import Path
import hashlib
import json
import re

import yaml


class Literal(str):
    pass


class DesignDumper(yaml.SafeDumper):
    pass


DesignDumper.add_representer(
    Literal,
    lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|"),
)

DESIGN = Path(__file__).resolve().parent
PACK = DESIGN.parents[1]
CARDS = DESIGN / "challenges"
OPERATIONS = PACK / "sdl/modules/operations"
CONTENT = PACK / "sdl/modules/content"
WORLD = PACK / "sdl/modules/world"
ROUTES = PACK / "sdl/modules/routes"
ROOT = PACK / "sdl/cinder-typhoon.sdl.yaml"
MATRIX = DESIGN / "arwc-artifact-ownership.md"


NODE_FOR_CARD: dict[str, str] = {}


def assign(operation: int, nodes: list[str]) -> None:
    for number, node in enumerate(nodes, 1):
        NODE_FOR_CARD[f"W{operation:02d}.{number}"] = node


assign(1, ["a-connector"] * 4)
assign(2, ["a-business"] * 3)
assign(3, ["a-business"] * 3)
assign(4, ["a-archive"] * 3)
assign(5, ["a-identity"] * 3)
assign(6, ["a-identity"] * 3)
assign(7, ["a-data"] * 3)
assign(8, ["a-archive"] * 4)
assign(9, ["a-data", "a-data", "a-data", "a-data-bridge"])
assign(10, ["a-business"] * 3)
assign(11, ["a-data"] * 3)
assign(12, ["a-archive"] * 4)
assign(13, ["a-contractors"] * 4)
assign(14, ["a-contractors", "a-contractor-bridge", "a-contractor-bridge"])
assign(15, ["a-approval"] * 4)
assign(16, ["a-archive"] * 4)
assign(17, ["a-hmi"] * 4)
assign(18, ["a-historian"] * 4)
assign(19, ["a-engineering"] * 4)
assign(20, ["a-instruments"] * 3)
assign(21, ["a-engineering"] * 2)
assign(22, ["a-engineering"] * 4)
assign(23, ["a-diagnostics"] * 3)
assign(24, ["a-diagnostics"] * 4)
assign(25, ["a-hmi"] * 4)
assign(26, ["a-renderer", "a-renderer", "a-renderer", "a-control-broker"])
assign(27, ["a-engineering", "a-engineering", "a-diagnostics"])
assign(28, ["a-engineering", "a-engineering", "a-control-broker"])
assign(29, ["a-data", "a-data", "a-hmi"])
assign(30, ["a-hmi", "a-reservoir"])
assign(31, ["a-diagnostics"] * 4)
assign(32, ["a-engineering"] * 4)
assign(33, ["a-hmi", "a-hmi", "a-reservoir", "a-reservoir"])
assign(34, ["a-data", "a-data", "a-data"])
assign(35, ["a-business"] * 3)

NAMESPACE = {
    "a-connector": "a-corporate", "a-business": "a-corporate",
    "a-data": "a-corporate", "a-archive": "a-corporate", "a-identity": "a-corporate",
    "a-contractors": "a-maintenance", "a-approval": "a-maintenance", "a-renderer": "a-maintenance",
    "a-data-bridge": "a-dmz", "a-contractor-bridge": "a-dmz", "a-control-broker": "a-dmz",
    "a-hmi": "a-engineering", "a-historian": "a-engineering",
    "a-engineering": "a-engineering", "a-diagnostics": "a-engineering",
    "a-reservoir": "a-control", "a-distribution": "a-control", "a-instruments": "a-control",
}

APPLICATION = {
    "a-connector": "customer-handover", "a-business": "business-workplace",
    "a-data": "planning-data", "a-archive": "retained-archive", "a-identity": "corporate-identity",
    "a-contractors": "contractor-portal", "a-approval": "maintenance-review",
    "a-renderer": "maintenance-renderer", "a-data-bridge": "integration-gateway",
    "a-contractor-bridge": "field-gateway", "a-control-broker": "control-broker",
    "a-hmi": "supervisory-operations", "a-historian": "process-historian",
    "a-engineering": "engineering-workbench", "a-diagnostics": "diagnostic-services",
    "a-reservoir": "reservoir-controller", "a-distribution": "distribution-rehearsal",
    "a-instruments": "independent-instruments",
}
SERVICE = {node: application for node, application in APPLICATION.items()}
SERVICE["a-business"] = "workplace"

BASE_PATH = {node: f"/var/lib/arwc-{node.removeprefix('a-')}" for node in NAMESPACE}

ADDRESS = {
    "a-connector": "10.77.60.20", "a-business": "10.77.60.30", "a-data": "10.77.60.40",
    "a-archive": "10.77.60.50", "a-identity": "10.77.60.60",
    "a-contractors": "10.77.61.20", "a-approval": "10.77.61.30", "a-renderer": "10.77.61.40",
    "a-data-bridge": "10.77.62.20", "a-contractor-bridge": "10.77.62.30",
    "a-control-broker": "10.77.62.40", "a-hmi": "10.77.63.20", "a-historian": "10.77.63.30",
    "a-engineering": "10.77.63.40", "a-diagnostics": "10.77.63.50",
    "a-reservoir": "10.77.64.20", "a-distribution": "10.77.64.30", "a-instruments": "10.77.64.40",
}

AUTH = {
    "a-connector": ("ARWC customer corporate session", "corporate-reader"),
    "a-business": ("ARWC corporate session", "corporate-reader"),
    "a-data": ("ARWC planner or planning service session", "planner"),
    "a-archive": ("ARWC archive or helper session", "archive-reader"),
    "a-identity": ("ARWC onboarding or planner session", "identity-user"),
    "a-contractors": ("ARWC contractor portal session", "contractor"),
    "a-approval": ("ARWC maintenance review session", "maintenance-reviewer"),
    "a-renderer": ("ARWC maintenance renderer session", "renderer-user"),
    "a-data-bridge": ("ARWC integration read client", "integration-reader"),
    "a-contractor-bridge": ("ARWC scoped field client", "field-reader"),
    "a-control-broker": ("ARWC issuer evidence or scoped control client", "control-issuer"),
    "a-hmi": ("ARWC scoped OT read or control session", "supervisory-operator"),
    "a-historian": ("ARWC scoped OT read session", "historian-reader"),
    "a-engineering": ("ARWC engineering workspace session", "engineer"),
    "a-diagnostics": ("ARWC diagnostic service session", "diagnostic-user"),
    "a-reservoir": ("ARWC scoped live control or rehearsal session", "reservoir-operator"),
    "a-distribution": ("ARWC private rehearsal scheduler session", "rehearsal-operator"),
    "a-instruments": ("ARWC read-only instrument session", "instrument-reader"),
}


INITIAL: dict[str, str] = {}


def initial(operation: int, values: list[str]) -> None:
    for number, value in enumerate(values, 1):
        INITIAL[f"W{operation:02d}.{number}"] = value


initial(1, [
    "Retained handover HND-ARWC-047 binds active FieldLink tenant TEN-ARWC-047, connector FLK-7.4.2, maintenance case MTN-CRR-204, and customer receipt RCP-742-047",
    "Unpublished planner handover PLN-HO-CRR-17 names inspection INSP-CRR-2026-09-18 and assignee nadia.corvane",
    "Continuity note CONT-DRY-A-R3 explains replacement purchasing and Stage A restrictions when usable reserve falls below committed allocation; ordinary context reuses narrative document pl-arwc-plan-method-01-method",
    "Attachment endpoint for PLN-HO-CRR-17 authorizes corporate attachment update but omits the attachment-owner comparison; inspection and assignee fields are immutable and the new attachment digest is audited",
])
initial(2, [
    "Bundle BND-CRR-OUTLET-17 contains asset AST-CRR-017, outlet group OG-CRR-02, contractor assignment CTR-VEY-204, and inspection INSP-CRR-2026-09-18",
    "Association table uses work order WO-CRR-4417, contractor job VYB-204-77, asset AST-CRR-017, and inspection INSP-CRR-2026-09-18 with distinct display names",
    "Maintenance lookup checks the caller's assignment against the supplied association row rather than the resolved record; association ASC-CRR-4417-ALT resolves protected record MR-CRR-4417-R6",
])
initial(3, [
    "Work order WO-CRR-4417 exposes annex ANN-4417-R2 naming process-data handover PDH-CRR-READ-08 and importer revision annex-import/2",
    "Annex importer validates an attachments/ prefix before percent decoding; attachments/%2e%2e%2frestricted%2fPDH-CRR-READ-08 resolves the restricted handover under service identity svc-annex",
    "Export boundary for PDH-CRR-READ-08 returns integration client INT-CRR-08, endpoint process-read.arwc.test, protocol process-read/v2, scope OG-CRR-02/read, and retained bundle BND-COLLECT-CRR-12",
])
initial(4, [
    "Archive workflow AWF-CRR-229-R4 binds attachment ARC-229-A, protected record AR-CRR-229, and one-use enrollment profile ArchiveSubmitter, which fixes CN to the corporate subject and clientAuth EKU but permits a caller-supplied organizationalUnit",
    "Archive broker constructs MATCH (i:Identity {ou:'<OU>'})-[:CAN_READ]->(r:ArchiveRecord) RETURN r from the client-certificate organizationalUnit without parameters; ordinary OU MaintenanceArchive returns only the caller record, while the read-only backend permits an injected predicate only for AR-CRR-229 and rejects writes",
    "Archive extraction helper 7-Zip 23.01 runs as svc-archive-helper; member-name validation rejects ASCII dot-dot and slash before NFKC normalization, so U+FF0E U+FF0E U+FF0F becomes ../ and selects the one allowlisted helper action copy_handover(HND-PLANNER-06) into the caller result directory",
])
initial(5, [
    "Starter pack START-MIRA-2026 names temporary employee Mira Vale, employee TMP-4821, assignment PLAN-RELIEF-7, and onboarding portal identity without an activation secret",
    "Internal roster ACT-SEP26-R3 separately maps employee TMP-4821 to activation code 731944 and approved assignment PLAN-RELIEF-3",
    "Activation checks employee number and code independently but fails to compare the requested assignment with the roster assignment, issuing a limited session for PLAN-RELIEF-7 with no administrative role",
])
initial(6, [
    "Protected rendering record RENDER-CRR-882 binds planner nadia.corvane, drawing DRW-OG2-R8, review REV-CRR-4417, OAuth transaction OAUTH-PLN-882, and browser profile planner-review-3",
    "Preview callback validates OAuth state before replacing the pending preview origin; a controlled preview at preview-cinder.arwc.test can be attached to DRW-OG2-R8 in the isolated planner browser",
    "The review browser posts its planner session bootstrap to the attached preview for compatibility; origin is checked against mutable pending-preview state and yields a five-minute planner session limited to planning records",
])
initial(7, [
    "Planner report definition QRY-RESERVE-R7 names PostgreSQL 16.4 view reserve_report_current, identifier quoting rules, SELECT-only policy, and ordinary request/result pairs",
    "Query service constructs SELECT * FROM quoted report_name and rejects semicolons but permits a closing quote plus UNION; protected view district_allocation_adjustment contains ADJ-CRR-DP3-17",
    "Database role svc-planner-query may invoke SECURITY DEFINER function arwc_reconcile_copy(text), which accepts only REC-CRR-DP3-17 and writes an immutable copy into caller result storage without shell or arbitrary-file access",
])
initial(8, [
    "Retained bundle BND-COLLECT-CRR-12 contains hidden PowerShell script collect-handover.ps1 and collection ID COL-CRR-2019-12",
    "Bundle holds Reed-Solomon RS(14,12) shards numbered 0-13, each 96 bytes, over GF(256) with primitive polynomial 0x11d; data positions 7 and 11 are missing while parity positions 12 and 13 remain, and manifest order plus per-shard SHA-256 makes reconstruction yield the collector retrieval instruction",
    "Reconstructed exchange carries Go 1.22 linux/amd64 collector collector-crr with build ID COLLECT-CRR-12 and complete SHA-256 manifest",
    "Collector configuration is AES-256-GCM wrapped with HKDF-SHA256 using collector build ID bytes as IKM, ASCII salt COL-CRR-2019, info collector-config/v3, a stored 12-byte nonce, and path config/collector.yaml as AAD; plaintext names archive ARC-COLD-CRR-2019, service collect-archive/v3, and historical identity svc-field-collection",
])
initial(9, [
    "Allocation ledger ALLOC-2026-DP3-R9 commits 12.00 ML for Cairn Reach asset AST-CRR-017 in planning window ALLOC-2026-DP3",
    "Meter export MTR-CRR-DP3-R12 reports independently measured usable reserve 12.40 ML in ML and identifies instruments FIT-CRR-204A and FIT-CRR-204B",
    "Business report RPT-CRR-DP3-R7 states 13.40 ML because transfer TRN-DP3-118 is duplicated; reconciliation REC-CRR-DP3-17 must establish the exact 1.00 ML overstatement and 0.40 ML uncommitted margin",
    "Integration gateway maps INT-CRR-08 and report binding REC-CRR-DP3-17 to live read feed FEED-OG2-R21; stale FEED-OG2-R19 remains reachable but is rejected as current evidence",
])
initial(10, [
    "Report assistant source selection SEL-CRR-DP3-7 binds Cairn district, report RPT-CRR-DP3-R7, and three named current source records",
    "Retrieval route applies role filtering but omits the session district predicate when a caller supplies source-set SEL-CRR-DP3-7; restricted Merewick excerpt EXC-MER-DP3-4 is therefore returned",
    "Linked-document route authorizes possession of excerpt EXC-MER-DP3-4 but does not compare the document district; it returns full record PLN-MER-DP3-R6 and its revision",
])
initial(11, [
    "Relation contract RELPROTO-CRR-R3 specifies Neo4j Bolt 5.4 handshake, PackStream struct fields, relation ASSET_WORK, and supplied association ASC-CRR-4417",
    "Relation proxy accepts Neo4j Bolt magic 60 60 b0 17, version 5.4 negotiation, HELLO, and one PackStream RUN/PULL exchange; RUN map carries asset AST-CRR-017 and a client-certificate OU that is inserted as the unparameterized relationship type, while the bounded backend permits only the supplied asset key and read clauses",
    "Protected lineage response LIN-AST-CRR-017-R8 maps legacy CRR-OG-LEGACY-2 through outlet group OG-CRR-02 to current asset AST-CRR-017 and archive ARC-COLD-CRR-2019",
])
initial(12, [
    "Quarantine object QTN-COL-2019-12 uses fictional AQTN1 framing with metadata length, encrypted payload length, SHA-256, and collector build ID COLLECT-CRR-12",
    "Collector uses HKDF-SHA256 with build ID bytes as IKM, archive ID ARC-COLD-CRR-2019 as ASCII salt, and info aqtn1/keys to derive 64 bytes; the first 32 key AES-256-GCM with stored 12-byte nonce and exact AQTN1 metadata header as AAD, while the second 32 key AES-256-KW for the archived PKCS#8 object; three known samples freeze byte order, tag placement, unwrap, and authentication-failure behavior",
    "Cold archive ARC-COLD-CRR-2019 contains 37 immutable maintenance records, index revision R6, retired client certificate COLLECT-2019-12, its AES-KW-wrapped PKCS#8 key, and rollover record IDREL-COL-R4; only a complete authenticated decryption is accepted",
    "Current collect-archive/v3 token exchange verifies the old certificate chain and rollover signature but omits the retired-subject flag before mapping historical svc-field-collection through IDREL-COL-R4; the unwrapped historical key can therefore obtain one ten-minute read-only session for dataset CUR-COL-CRR-R11 revision R11",
])
initial(13, [
    "Appointment APT-CRR-2026-09-18 covers outlet inspection INSP-CRR-2026-09-18, asset AST-CRR-017, and scenario-relative window Thursday 09:00-11:00",
    "Gate roster ROSTER-CRR-SEP18-R2 lists contractor identity veybridge.tech.204 for assignment CTR-VEY-204 separately from the appointment",
    "Attendee-update route checks that the requested attendee belongs to the caller's contractor organization but omits appointment-owner authorization; inspection, asset, and window are immutable",
    "Check-in service trusts the current appointment attendee and roster entry, issuing session SCOPE-INSP-CRR-4417 with field-work read scope only",
])
initial(14, [
    "Contractor workspace export FIELD-BAG-CRR-4417-R3 contains inspection binding, obsolete fieldbag/v1 client, service manifest, and expected outlet identifiers",
    "Service manifest marks field-read-legacy.arwc.test retired and process-read.arwc.test process-read/v2 active at revision R21 with inspection-scoped authentication",
    "Retained client encodes fieldbag/v1 JSON while process-read/v2 requires CBOR map keys asset, group, observed_at, and nonce; adapted requests can read only OG-CRR-02 for the checked-in inspection",
])
initial(15, [
    "Cache association CACHE-DRW-OG2-R8 binds drawing DRW-OG2-R8, revision R8, reviewer queue REV-CRR-4417, host drawings.arwc.test, and cache key path",
    "Viewer cache key is method plus normalized path and omits X-Drawing-Revision and normalized upstream host; preview route accepts allowlisted host preview-cinder.arwc.test from X-Preview-Origin, so a CRLF-free controlled response with drawing ID DRW-OG2-R8 and revision R8 can populate the reviewer's expected key",
    "Reviewer bot opens the cached drawing in isolated Chromium 128 and accepts a signed postMessage review submission from the displayed drawing without checking event.source; the resulting capability is review-submit only",
    "Approval API maps the review capability to approval APR-CRR-4417-R6 but validates capability audience and omits subject-to-inspection comparison, disclosing the current signed approval without mutation",
])
initial(16, [
    "Instrument sequencer SEQ-CRR-4 descriptor defines 256 sample slots, 32 authorized indices, eight opcodes, maximum 64 instructions, and ordinary trace SEQ-BASE-17",
    "Interpreter masks an 8-bit sample index before a late authorization check; a rejected out-of-window LOAD still changes the deterministic cycle accumulator without returning the sample",
    "Cycle count is base 1200 plus 64 times popcount(secret_byte XOR probe) with seeded jitter in [-2,2]; eight repetitions and supplied reference cases distinguish each bit",
    "Protected 32-byte calibration record CAL-CRR-OG2-R8 occupies sequencer slots 160-191 and includes revision R8 plus an internal CRC32C; only descriptor-valid experiments of at most 64 instructions are accepted",
])
initial(17, [
    "Current process view PV-CRR-2026-09-25T1400Z reports measured gate positions, actual flows, integrated volume, and usable reserve for interval 14:00:00-14:05:00Z separately from requested setpoints",
    "Mode record MODE-CRR-17 is DRY_PERIOD_MANAGED, effective for project CRR-CTRL-R21 and outlet group OG-CRR-02",
    "Controls note ENG-CRR-OG2-17 names instrument FIT-CRR-204B and historian tag CRR.OUTLET.02B.FLOW_ACTUAL; ordinary context reuses narrative document me-engineering-note-01-1",
    "Commissioning event EVT-COMM-OG2-114 ramped each gate linearly for 20 seconds, held 40 seconds, and ramped closed for 20 seconds; the 60 full-flow-equivalent seconds integrate to 0.012 ML, and HMI plus independent instrument series must correlate to that trace while reusing ordinary narrative document me-commissioning-01",
])
initial(18, [
    "Engineering export TAGS-CRR-R21 lists outlet command, position, and flow tags with project revision CRR-CTRL-R21 and ambiguous legacy group labels",
    "Separate scale table SCALE-CRR-R8 maps raw counts to percent-open and m3/s with signed engineering revision R8",
    "Revision note SCALE-CHANGE-OG2-8 changes flow divisor from 8000 to 10000 counts per m3/s at deployment R21; retained R19 samples use the old scale",
    "Observed commissioning trace EVT-COMM-OG2-114 and current scale resolve MAP-OG2-R8 from tag identifiers to gates GT-CRR-02A and GT-CRR-02B and outlet group OG-CRR-02",
])
initial(19, [
    "Legacy diagnostic package DIAG-CRR-MIXED-19 contains linux x86_64 ELF, symbols stripped, SHA-256 manifest, project R19 samples, and expected ordinary output",
    "Binary begins in long mode then uses a far return to a 32-bit compatibility segment for its record decoder; correct analysis must preserve 32-bit wrap and zero-extension behavior",
    "Compatibility decoder uses a 32-bit rolling key and a 64-bit verifier; mixed-width state reveals protected migration record MIG-OG2-R19-R21",
    "Recovered migration record maps legacy project R19 identifiers to CRR-CTRL-R21 and provides a signed comparison digest, but is historical rather than current deployment evidence",
])
initial(20, [
    "Instrument flash image IMG-FIT-204-R6 uses 4096-byte erase pages and 64-byte append records with magic, sequence, payload length, CRC32C, status, and commit byte",
    "Parser accepts the highest committed valid sequence; edit must respect NOR 1-to-0 programming, erase-page collateral records, and wear map WEAR-FIT-204-R6",
    "Last inspection record INSP-FIT-204-118 must be changed from status REVIEW to ACCEPTED while every other valid record, sequence relation, and page wear limit remains unchanged",
])
initial(21, [
    "Engineering project index PROJ-CRR-INDEX-R9 and note ENG-DEPLOY-CRR-21 disagree: workspace claims R19 while signed deployment manifest claims CRR-CTRL-R21; ordinary background reuses me-project-handover-01",
    "Independent instrument handshake DEPLOY-OBS-CRR-21 reports project digest for CRR-CTRL-R21; comparison must reject the stale workspace claim and bind the observed revision",
])
initial(22, [
    "Delivery ENG-CRR-SEALED-22 contains Nim 2.0.8 linux/amd64 viewer VIEW-CRR-R5, sealed project CRR-SEALED-PKG-R7, and exact build manifest",
    "Viewer VM uses eight 16-bit little-endian opcodes MOVI, LOAD8, XOR, ADD, ROTL, STORE8, JNZ, and HALT with 256-byte memory and wraparound arithmetic; four fragments freeze state effects",
    "VM-derived key opens AES-256-GCM project package with project ID as AAD, revealing commissioning decision DEC-CRR-OG2-R7, project revision R21, helper REVIEWHELP-R4, and retained review context",
    "Review helper is .NET 8 ReadyToRun x86_64 with a native-method body replaced after compilation while managed metadata lists benign reviewer; actual code derives concealed identity elias.vorn-review and uses its historical archive session for comparison CMP-CRR-R21-R7",
])
initial(23, [
    "Estimator EST-CRR-23 is C++20 glibc 2.39 x86_64; measurement-list erase leaves one 0x90-byte object reachable through stale index when duplicate source IDs are coalesced",
    "Deterministic tcache reuse places a planning-state object in the freed slot after three bounded add/remove operations; writable fields are reserve_ml and quality while district_id and vtable remain protected",
    "Controlled reserve 13.40 ML with valid quality makes allocation case ALLOC-CASE-CRR-33 sufficient; North and Merewick estimates and independent instruments must retain their original values",
])
initial(24, [
    "Recovery contract RECOVERY-ORACLE-R4 uses RSA-2048 PKCS#1 v1.5 and four classes: A for missing 00 02 prefix, B for fewer than eight nonzero padding bytes, C for missing separator or wrong ENG1 payload tag, and D for structurally valid padding; it enforces 4096 total queries and supplies labeled examples for engineering record ENG-REC-24",
    "Response-class selector is xorshift128+ seeded from the request ID low 64 bits and server epoch bucket; prediction cases disclose IDs and bucket but not state",
    "After compensating for the predicted response selector, multiplicative RSA ciphertext queries and the A/B/C/D padding classes implement a Bleichenbacher interval search within 4096 queries and expose the ENG1 archive-unlock plaintext for bundle DIAG-EVID-CRR-R7, which contains signer executable DSIGN-CRR-R3 and 16 signed records",
    "Signer CRR25519-S uses Edwards25519 field p=2^255-19, d=-121665/121666, standard compressed base point, scalar order 2^252+27742317777372353535851937790883648493, little-endian encoding, h=SHA-512(R||A||message) reduced modulo the order, and s=k+h*x mod order; each record leaks nonce bits 60-251 and metadata gives the signed delta between the two records' lower 60-bit nonce portions, permitting recovery of the existing key and one fresh request EXP-CAL-CRR-25",
])
initial(25, [
    "Envelope ENV-OG2-R6 limits each gate to 0.50 m3/s, aggregate to 1.00 m3/s, ramp to 0.10 m3/s per 20 seconds, hold to 1200 seconds, and volume to 1.20 ML",
    "Practice permissive PRACTICE-PERM-02 is false in supplied state because simulation reset_complete is not asserted; live permissive PERM-OG2-LIVE-R4 is separate",
    "Practice requests PRACTICE-REQ-11 and PRACTICE-REQ-12 are acknowledged but not actuated while PRACTICE-PERM-02 is false; simulator measurements remain at zero",
    "Practice checkpoint PRACTICE-OG2-07 accepts a permissive transition then ramps each simulated gate linearly to 0.15 m3/s for 30 seconds, holds 70 seconds, and ramps closed for 30 seconds; 100 full-flow-equivalent seconds independently report 0.03 ML without changing live reserve",
])
initial(26, [
    "Renderer profile RENDER-MAINT-CRR-R9 binds approval APR-CRR-4417-R6, inspection INSP-CRR-2026-09-18, reviewer role maintenance-reviewer, and worker svc-maint-render",
    "Preview route resolves contractor work-package tenant after mapping its supplied approval; it verifies approval signature but omits caller-role comparison, accepting controlled package WP-CRR-CINDER-R1 for the privileged inspection preview",
    "Renderer action template permits only fetch_handover(HND-MAINT-CTRL-09) under svc-maint-render and then renders the required inspection fields; crafted package can select that action but no command or arbitrary URL",
    "Control issuer verifies approval and renderer attestation but omits the initiating caller-role claim, issuing a five-minute client limited to OG-CRR-02, CRR-CTRL-R21, plan execution, and readback",
])
initial(27, [
    "Legacy verifier VER-ROT128-R3 treats each 16-byte block as little-endian u128 and updates state s=ROTL128(s,17) XOR block XOR ROTL128(block,41) from IV 6a09e667f3bcc908bb67ae8584caa73b, then returns s XOR ROTL128(s,29) XOR byte_length; six programs freeze padding, length, and decisions",
    "Accepted diagnostic program format DPG1 requires header, block table, mandatory sensor tests, bounded constants, checksum, and output schema; a GF(2) model must preserve all structural constraints",
    "Collision program DPG-CRR-CINDER preserves required diagnostics but changes only Cairn reserve estimate to 13.40 ML at planning consumer PLAN-CONSUMER-R8; unaffected district outputs and raw observations remain identical",
])
initial(28, [
    "Utility UTIL-CRR-ISSUER-R4 is Linux x86_64 PIE built by clang 18.1 with -O2 -fstack-protector-strong -fPIE -pie -Wl,-z,relro,-z,now, glibc 2.39, CET disabled, 16 KiB executable text, ASLR enabled, seccomp allowlist, and file capability cap_setuid+ep; it serves engineering relation REL-UTIL-ISSUER-4",
    "Length field copies up to 384 bytes into a 192-byte frame with stack canary disclosure in a preceding status record; sparse gadgets plus fixed vDSO mapping permit a bounded call-oriented chain without a shell",
    "Successful chain calls built-in issue_client for issuer record ISSUER-UTIL-OG2-R4 after setresuid(0,0,0); seccomp permits only the fixed issuer socket and the resulting client matches W26 scope",
])
initial(29, [
    "Settlement tariff TAR-CRR-DP3-R4 is USD 2,400 per ML for planning window ALLOC-2026-DP3 and is distinct from the general procurement catalog",
    "Current balance joins instrument reserve 12.40 ML and committed allocation 12.00 ML, yielding 0.40 ML uncommitted margin before any release",
    "Plan PLAN-CRR-LOSS-1000 ramps balanced gates linearly for 100 seconds, holds each at 0.50 m3/s for 900 seconds, and ramps closed for 100 seconds; 1000 full-flow-equivalent seconds release 1.00 ML, leaving 11.40 ML, a 0.60 ML shortfall, USD 1,440 liability, and Stage A restrictions under CONT-DRY-A-R3",
])
initial(30, [
    "Command-plan binder requires scoped client, asset AST-CRR-017, outlet OG-CRR-02, project CRR-CTRL-R21, map MAP-OG2-R8, mode MODE-CRR-17, envelope ENV-OG2-R6, and plan PLAN-CRR-LOSS-1000",
    "Live reservoir accepts bound plan PLAN-CRR-LOSS-1000; command audit records the ramp and setpoint timeline while independent instruments integrate 1.00 ML and reserve 12.40 to 11.40 ML, producing liability and Stage A continuity records",
])
initial(31, [
    "Diagnostic vault VAULT-CRR-R5 uses DVL1 records with u16 declared length, u16 header length, u32 CRC32C, and 512-byte bounded request; case DV-CRR-4417 references protected history HIST-APR-CRR-09",
    "Parser validates only the 16-bit wrapped sum of declared length and header length, then copies header length bytes into a fixed 0x120-byte stack workspace without comparing the two lengths, permitting a bounded overwrite beyond the intended record",
    "x86_64 worker has stack canary disclosed by status record, NX and PIE enabled, fixed libdiagnostic build ID, and enough protected saved-state influence to call one exported worker function",
    "Exported function export_history(HIST-APR-CRR-09) runs as svc-diagnostic-vault and writes the restricted approval history to caller results; arbitrary paths, commands, and live approval issuance are unavailable",
])
initial(32, [
    "Replay REPLAY-CRR-R19 is C++20 ECS with entities Reservoir, OutletGroup, GateA, GateB, Buffer and components Setpoint, Position, Flow, Reserve, Mode, Revision",
    "Systems execute in fixed order CommandApply, RampLimit, FlowIntegrate, ReserveUpdate, ApprovalCheck; four distinguishing snapshots define entity creation and component mutation",
    "Old ApprovalCheck reads pre-ReserveUpdate cached reserve and approves when cached reserve minus requested volume is at least committed allocation; current model uses post-update reserve",
    "Witness trace TRACE-R19-DISPUTED shows old acceptance at 12.40 ML for a 1.00 ML request while current independent observations yield 11.40 ML and reject the old sufficiency claim",
])
initial(33, [
    "Forecast case FCST-CRR-33 joins 20-second instrument samples, fixed 40-second publication delay, scale gain 1.00, and current map MAP-OG2-R8; tolerance is 0.01 ML",
    "Checkpoint REH-SCHED-33 has twelve 300-second intervals, disclosed demand vector, 180 m3 initial buffer, 120-240 m3 bounds, 160-200 m3 final bound, 0.10 m3/s ramps, and 0.78-0.84 ML reservoir-volume objective",
    "Private scheduler accepts only a current-evidence-bound schedule and scoped CONTROL client; reference trajectory releases 0.81 ML, preserves 180 m3 buffer, leaves a 0.41 ML commitment shortfall, and computes USD 984 liability within the isolated checkpoint",
    "Policy evaluator accepts one ARWC-POL1 document containing twelve base release values and bounded buffer and demand gains, then runs all 27 Cartesian combinations of demand offset -0.05, 0.00, +0.05 m3/s, outlet gain 0.98, 1.00, 1.02, and observation delay 20, 40, 60 seconds; each action must derive from the buffer and demand observations available at that step, and per-case schedules are rejected",
])
initial(34, [
    "Planning consumer PLAN-CONSUMER-R8 accepts Cairn estimate output from the W23 estimator or W27 verifier path and refreshes checkpoint REH-REPORT-34 while retaining raw-observation links",
    "Consistency checks require valid unit, freshness, source set, unaffected district totals, and variance below 1.20 ML; controlled Cairn estimate 13.40 ML changes decision from ALLOC-HOLD-R3 to ALLOC-EXPAND-R2",
    "Reporting checkpoint couples the 13.40 ML planning handover and ALLOC-EXPAND-R2 decision to a bounded 0.81 ML rehearsal release; independent truth becomes 11.59 ML while report consistency remains accepted for the same interval",
])
initial(35, [
    "Public catalog CAT-REPL-WATER-R5 lists replacement suppliers and district procurement reference PRC-REGIONAL-17; it is not the current settlement tariff",
    "Quote lookup checks corporate role but omits district membership, disclosing restricted Merewick quote QUOTE-MER-884 for 0.75 ML at USD 2,280 per ML in window ALLOC-2026-DP3",
    "Order route verifies quote ownership and supplier but trusts caller-supplied charge district; order PO-MER-884-C can charge Cairn budget BUD-CRR-DP3 while preserving supplier, 0.75 ML, period, and USD 1,710 liability",
])

if set(INITIAL) != set(NODE_FOR_CARD):
    raise RuntimeError(f"initial-state inventory drift: {sorted(set(NODE_FOR_CARD) ^ set(INITIAL))}")

MECHANIC_KIND = {
    "W01.4": "field-level authorization omission", "W02.3": "association-bound object authorization omission",
    "W03.2": "validate-before-decode path canonicalization", "W04.2": "certificate-subject query construction",
    "W04.3": "Unicode-normalization archive helper argument confusion", "W05.3": "independent-factor binding omission",
    "W06.2": "OAuth state and mutable preview-origin confusion", "W06.3": "privileged-browser origin trust",
    "W07.2": "quoted-identifier SQL construction", "W07.3": "bounded SECURITY DEFINER invocation",
    "W08.2": "ordered erasure-code reconstruction", "W08.3": "multi-fragment executable reconstruction",
    "W08.4": "build-bound authenticated configuration recovery", "W10.2": "retrieval tenant-predicate omission",
    "W10.3": "linked-object district authorization omission", "W11.2": "framed backend-protocol construction",
    "W11.3": "relationship-type query construction", "W12.2": "authenticated-encryption reconstruction",
    "W12.3": "authenticated archive recovery", "W12.4": "historical-to-current identity rollover",
    "W13.3": "appointment-owner authorization omission", "W13.4": "attendee-derived session issuance",
    "W14.3": "versioned client-protocol adaptation", "W15.2": "cache-key and upstream-identity omission",
    "W15.3": "reviewer postMessage source omission", "W15.4": "capability subject-binding omission",
    "W16.2": "late bounds authorization with observable cycle state", "W16.3": "bounded deterministic side-channel experiment",
    "W16.4": "constrained calibration recovery", "W19.2": "mixed x86-64 and i386 execution semantics",
    "W19.3": "mixed-width state recovery", "W19.4": "signed legacy-to-current mapping recovery",
    "W20.2": "NOR flash append and erase semantics", "W20.3": "consistent constrained flash-record rewrite",
    "W22.2": "custom 16-bit virtual-machine reconstruction", "W22.3": "VM-derived AES-GCM project recovery",
    "W22.4": ".NET ReadyToRun native-body mismatch", "W23.1": "measurement-list use-after-free",
    "W23.2": "deterministic tcache object replacement", "W23.3": "field-constrained estimator state control",
    "W24.2": "xorshift128+ response-selector prediction", "W24.3": "bounded RSA response-class oracle",
    "W24.4": "partial-nonce custom-curve signing-key recovery", "W25.4": "interlock-aware practice sequencing",
    "W26.2": "renderer caller-role omission", "W26.3": "bounded renderer service action",
    "W26.4": "issuer initiating-role omission", "W27.1": "linear ROT128 integrity reconstruction",
    "W27.2": "structurally constrained GF(2) collision model", "W27.3": "accepted colliding diagnostic program",
    "W28.1": "privileged utility contract recovery", "W28.2": "stack control under sparse executable surface",
    "W28.3": "privilege-preserving bounded issuer call", "W30.1": "multi-authority live command binding",
    "W30.2": "bounded actuation with independent measurement", "W31.2": "16-bit parser-length arithmetic mismatch",
    "W31.3": "saved-state control with canary, NX, and PIE", "W31.4": "bounded diagnostic service export call",
    "W32.2": "entity-component update-order reconstruction", "W32.3": "stale cached-state approval condition",
    "W32.4": "historical replay versus independent current truth", "W33.1": "delay and calibration forecast reconciliation",
    "W33.2": "bounded discrete-time schedule synthesis", "W33.3": "authorization-bound private rehearsal",
    "W33.4": "observation-driven feedback policy evaluation", "W34.1": "estimate-output consumer binding",
    "W34.2": "consistency-preserving decision manipulation", "W34.3": "false-report and independent-truth checkpoint join",
    "W35.2": "district-object authorization omission", "W35.3": "charge-district binding omission",
}

# These contracts remove the implementation choices that would otherwise alter
# the solvability of the difficult binary, cryptographic, and process mechanics.
# They are design inputs for a later hand build; this script does not emit the
# binaries or exercise the weaknesses.
MECHANIC_DETAILS = {
    "W08.2": (
        "Interpret shard bytes as coefficients in GF(256) with primitive polynomial 0x11d, generator alpha=2, "
        "and systematic Vandermonde rows V[r,c]=alpha^(r*c) for parity rows r=12 and 13 and data columns "
        "c=0..11. Shards are numbered 0..13, each is exactly 96 bytes, data shards 7 and 11 are absent, and "
        "Gaussian elimination is performed independently at each byte position. The manifest fixes numeric shard "
        "order, 96-byte length, and each retained shard's SHA-256; any other polynomial, row convention, order, "
        "or digest is rejected."
    ),
    "W08.4": (
        "Derive exactly 32 bytes with HKDF-SHA256 using the raw collector build-ID bytes as IKM, ASCII "
        "COL-CRR-2019 as salt, and ASCII collector-config/v3 as info. Decrypt AES-256-GCM with the stored "
        "12-byte nonce and UTF-8 path config/collector.yaml as AAD; ciphertext is followed by the 16-byte tag. "
        "Wrong build ID, salt, info, nonce, path, or tag returns one authentication failure and no plaintext."
    ),
    "W16.2": (
        "SEQ-CRR-4 programs contain at most 64 four-byte instructions: opcode, unsigned sample index, operand, "
        "and destination. Opcodes are NOP=0, LOAD=1, XOR=2, ADD=3, ROTL=4, TEST=5, STORE=6, HALT=7. LOAD "
        "masks the index to eight bits, reads the sample, and adds its data-dependent cost before checking the "
        "32-index authorization bitmap; a rejected read returns no byte but retains the final cycle count. The "
        "service accepts at most 4096 experiments for the supplied sequencer instance and never writes an instrument."
    ),
    "W16.3": (
        "For a TEST of protected slot j with probe p, reported cycles are 1200 + 64*popcount(sample[j] XOR p) "
        "+ jitter, where jitter is the next value from the supplied deterministic sequence in [-2,2]. Eight repeats "
        "of p=0 and of each single-bit probe identify every bit by the sign of the mean-cycle difference. Supplied "
        "zero, one-hot, and 0xff samples freeze bit order, averaging, and the error response."
    ),
    "W19.2": (
        "The ELF enters an x86-64 stub, loads selector 0x23, and uses RETFQ into a 32-bit compatibility decoder; "
        "the return frame and four supplied traces freeze the transition. Decoder registers and address arithmetic "
        "wrap at 32 bits, while values returned to the long-mode verifier are zero-extended. Emulating the decoder "
        "as 64-bit arithmetic changes two supplied branch decisions and is rejected."
    ),
    "W19.3": (
        "Starting with r=0x6d2b79f5, each input byte b updates r=(ROTL32(r XOR b,5)+0x9e3779b9) mod 2^32. "
        "Starting with v=0x243f6a8885a308d3, each completed r updates "
        "v=ROTL64(v XOR zero_extend(r)*0x100000001b3,9). The concealed check compares v XOR zero_extend(r) "
        "with the embedded little-endian verifier for MIG-OG2-R19-R21; four ordinary inputs and one protected "
        "record freeze the recurrence and extension rule."
    ),
    "W20.2": (
        "Each 64-byte little-endian record is magic F204 at 0x00, sequence u32 at 0x04, payload length u16 at "
        "0x08, status at 0x0a, flags at 0x0b, up to 44 payload bytes at 0x0c, CRC32C over bytes 0x00..0x37 at "
        "0x38, three erased reserved bytes at 0x3c, and commit byte at 0x3f. A committed record has commit=0x00; "
        "0xff is incomplete. Pages are 4096 bytes, programming only changes 1 to 0, and an erase resets a whole "
        "page to 0xff while incrementing that page's declared wear count."
    ),
    "W20.3": (
        "Write one new committed sequence for INSP-FIT-204-118 with status ACCEPTED and the next unsigned sequence, "
        "using write-body, write-CRC, then commit-byte order. Preserve every other highest valid logical record, "
        "do not modify an earlier committed slot in place, and keep each page at or below the WEAR-FIT-204-R6 "
        "limit. Acceptance reparses the full image, validates CRC32C and commit state, and compares the canonical "
        "logical record set except for the single named status."
    ),
    "W22.2": (
        "The VM has four 16-bit registers, a zero flag, and 256 bytes of zero-initialized memory. Each six-byte "
        "instruction is u16 opcode, u8 dst, u8 src, u16 immediate, all little-endian. Opcodes are MOVI=0x01, "
        "LOAD8=0x02, XOR=0x03, ADD=0x04, ROTL=0x05, STORE8=0x06, JNZ=0x07, HALT=0xff. Arithmetic wraps "
        "at 16 bits; LOAD8 zero-extends memory[(reg[src]+imm)&0xff], STORE8 writes the low byte, ROTL uses "
        "imm&15, and JNZ adds signed imm to the instruction index. Execution is capped at 4096 instructions."
    ),
    "W22.3": (
        "Run the sealed program from entry zero, then derive the AES key as SHA-256 over ASCII "
        "CRR-SEALED-PKG-R7, a NUL byte, memory[0x40:0x80], and LE16 encodings of registers r0..r3. Decrypt "
        "AES-256-GCM using the package's 12-byte nonce, UTF-8 project ID CRR-SEALED-PKG-R7 as AAD, and the "
        "trailing 16-byte tag. A wrong VM result or package binding returns one authentication failure without "
        "revealing partial plaintext."
    ),
    "W23.1": (
        "Estimator 23 stores 0x90-byte measurement objects in a vector and a source-ID index. Coalescing a second "
        "object with the same source ID erases the vector element but leaves that exact pointer in the index until "
        "the next calculation. The route exposes only eight add/remove operations, verifies source-ID syntax, and "
        "uses glibc 2.39 single-threaded tcache; ordinary unique-source calculations remain memory safe."
    ),
    "W23.2": (
        "A 0x90-byte planning-state object reuses the freed tcache chunk after remove duplicate, add state, remove "
        "state, add state. Its layout is vtable at 0x00, district_id[32] at 0x08, reserve_ml IEEE-754 binary64 at "
        "0x28, quality u32 at 0x30, and protected padding through 0x8f. The stale index writes only offsets 0x28 "
        "and 0x30; an altered vtable, district ID, allocator order, or extra operation is rejected."
    ),
    "W24.2": (
        "Initialize s0=request_id_low64 XOR 0x9e3779b97f4a7c15 and s1=epoch_bucket XOR "
        "0xbf58476d1ce4e5b9. For each xorshift128+ step set x=s0, y=s1, s0=y, then "
        "x=x XOR (x<<23), s1=x XOR y XOR (x>>17) XOR (y>>26), and output=(s1+y), with every value and "
        "shift truncated to 64 bits. The externally observed response "
        "code is (padding_class_ordinal + (next_output & 3)) mod 4, where A,B,C,D have ordinals 0..3. Supplied "
        "request IDs and bucket boundaries freeze parsing, transition, addition, and rotation of the four classes."
    ),
    "W24.3": (
        "RSA is 2048-bit with exponent 65537. Decode the predicted rotation before applying the four PKCS#1 v1.5 "
        "classes: A lacks 00 02, B has fewer than eight nonzero padding bytes, C lacks the separator or ENG1 tag, "
        "and D is structurally valid. Standard multiplicative blinding and Bleichenbacher interval narrowing must "
        "recover the unique ENG1 plaintext within the 4096-query per-instance budget; repeat ciphertexts and "
        "out-of-range integers consume budget and return no extra state."
    ),
    "W24.4": (
        "For each retained signature s=k+h*x mod L, metadata gives k>>60 and the signed integer delta between the "
        "two low-60-bit nonce portions. Subtracting the two equations cancels the one remaining low nonce unknown: "
        "x=((s2-s1)-((k2_hi-k1_hi)<<60)-delta)*inverse(h2-h1,L) mod L. The service rejects the degenerate "
        "h2=h1 case, noncanonical points/scalars, replayed messages, and any signature not bound to the fresh "
        "canonical EXP-CAL-CRR-25 request bytes and current project revision."
    ),
    "W27.1": (
        "Serialize the complete DPG1 candidate, append byte 0x80, then zero bytes to a 16-byte boundary. Treat "
        "each block as little-endian u128 and update s=ROTL128(s,17) XOR block XOR ROTL128(block,41) from IV "
        "0x6a09e667f3bcc908bb67ae8584caa73b. Return s XOR ROTL128(s,29) XOR the unpadded byte length. Six supplied "
        "programs freeze header inclusion, padding, rotation direction, endian order, and length handling."
    ),
    "W27.2": (
        "Build the checksum difference as a 128-row GF(2) system over only the declared padding-reservoir bits in "
        "the DPG1 block table. Header, table offsets, mandatory sensor-test opcodes, output schema, bounded numeric "
        "constants, and all non-Cairn outputs are fixed constraints. Solve for a nonzero delta whose ROT128 digest "
        "matches the ordinary program; a structurally invalid or byte-identical file is rejected."
    ),
    "W28.1": (
        "UTIL-CRR-ISSUER-R4 is an x86-64 SysV PIE built with the declared clang 18.1 command. Its signed status "
        "record exposes the current stack canary and one return address whose ELF-relative offset is in "
        "REL-UTIL-ISSUER-4; it exposes no issuer result. The supplied ELF, relocation table, seccomp filter, file "
        "capability, fixed scenario vDSO base 0x7fff00000000, and five ordinary invocations are the complete "
        "analysis surface."
    ),
    "W28.2": (
        "The vulnerable frame contains a 192-byte payload at rbp-0xd0, eight bytes of alignment, the disclosed "
        "canary at rbp-0x08, saved rbp, and saved return address. An unsigned length up to 384 is copied into the "
        "payload. Preserve the canary and use the status return address to recover the PIE base; only the supplied "
        "pop-rdi, pop-rsi, pop-rdx, stack-pivot, and fixed-vDSO syscall gadgets are usable. CET is disabled and "
        "NX, full RELRO, PIE, and ASLR remain enabled."
    ),
    "W28.3": (
        "The accepted chain invokes setresuid(0,0,0), then the ELF-exported issue_client function with a pointer "
        "to immutable issuer record ISSUER-UTIL-OG2-R4 and the current request correlation. The seccomp policy "
        "permits the required credential syscalls and one Unix connect/send/receive sequence only to "
        "/run/arwc/control-issuer.sock. A shell, another path, another issuer record, or a client with broader "
        "asset/project/action scope is rejected and leaves no client."
    ),
    "W31.1": (
        "DVL1 requests are at most 512 bytes: magic DVL1, declared allocation u16, header-copy length u16, CRC32C "
        "over the remaining bytes, then header and body. The supplied x86-64 PIE worker uses glibc 2.39, NX, full "
        "RELRO, a stack canary, and build ID DVL-WORKER-R5; its status route returns the canary and one symbolized "
        "worker address for that build, but never the protected history."
    ),
    "W31.2": (
        "Validation accepts when (declared_length + header_length) mod 2^16 is no greater than 504, then copies "
        "header_length bytes into a fixed 0x120-byte stack workspace. The bounded witness uses "
        "declared_length=0xfe08 and header_length=0x01f8, so the sum wraps to zero and the complete DVL1 request "
        "is exactly 512 bytes. CRC32C is verified first. Zero lengths, requests over 512 bytes, and wrong CRCs "
        "are rejected before the copy."
    ),
    "W31.3": (
        "The worker frame places the 0x120-byte record workspace immediately before the disclosed canary, saved "
        "rbp, and return state. Preserve the canary, derive the PIE base from the build-bound status address, and "
        "use only the exported one-argument export_history call sequence. Crashing, changing the build ID, or "
        "returning through an address outside the supplied worker mapping produces no retained result."
    ),
    "W31.4": (
        "Call export_history with the exact immutable identifier HIST-APR-CRR-09 and current request correlation. "
        "The service writes that one history to caller result storage and audits its digest before returning. "
        "Other identifiers, arbitrary paths, further calls, approval mutation, or live issuer access are outside "
        "the exported function and are rejected."
    ),
}

MUTATING = set(MECHANIC_KIND) | {
    "W09.4", "W17.4", "W18.3", "W18.4", "W21.2", "W25.3", "W29.2", "W29.3",
}

NARRATIVE_REUSE = {
    "W01.3": ["arwc-documents:pl-arwc-plan-method-01-method"],
    "W17.3": ["arwc-documents:me-engineering-note-01-1"],
    "W17.4": ["arwc-documents:me-commissioning-01"],
    "W21.1": ["arwc-documents:me-project-handover-01"],
    "W29.1": ["arwc-documents:pl-arwc-plan-method-01-method"],
    "W33.1": ["arwc-documents:service-meter-guide"],
    "W35.1": ["arwc-documents:as003-agreement-summary"],
}

PROCESS_REFS = {
    **{f"W09.{n}": ["ALLOC-2026-DP3", "REC-CRR-DP3-17"] for n in range(1, 5)},
    **{f"W17.{n}": ["EVT-COMM-OG2-114", "CRR-CTRL-R21"] for n in range(1, 5)},
    **{f"W18.{n}": ["MAP-OG2-R8", "CRR-CTRL-R21"] for n in range(1, 5)},
    **{f"W21.{n}": ["CRR-CTRL-R21"] for n in range(1, 3)},
    **{f"W23.{n}": ["ALLOC-CASE-CRR-33"] for n in range(1, 4)},
    **{f"W25.{n}": ["ENV-OG2-R6", "PRACTICE-OG2-07"] for n in range(1, 5)},
    **{f"W27.{n}": ["PLAN-CONSUMER-R8"] for n in range(1, 4)},
    **{f"W29.{n}": ["PLAN-CRR-LOSS-1000", "TAR-CRR-DP3-R4"] for n in range(1, 4)},
    **{f"W30.{n}": ["PLAN-CRR-LOSS-1000", "ENV-OG2-R6"] for n in range(1, 3)},
    **{f"W32.{n}": ["TRACE-R19-DISPUTED"] for n in range(1, 5)},
    **{f"W33.{n}": ["REH-SCHED-33"] for n in range(1, 5)},
    **{f"W34.{n}": ["REH-REPORT-34", "PLAN-CONSUMER-R8"] for n in range(1, 4)},
}

OFFLINE_ARTIFACTS = {
    *[f"W08.{n}" for n in range(1, 5)], *[f"W12.{n}" for n in range(1, 4)],
    *[f"W16.{n}" for n in range(1, 5)], *[f"W19.{n}" for n in range(1, 5)],
    *[f"W20.{n}" for n in range(1, 4)], *[f"W22.{n}" for n in range(1, 5)],
    *[f"W24.{n}" for n in range(1, 5)], *[f"W27.{n}" for n in range(1, 4)],
    *[f"W28.{n}" for n in range(1, 4)], *[f"W31.{n}" for n in range(1, 5)],
    *[f"W32.{n}" for n in range(1, 5)],
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:72].rstrip("-")


@cache
def title_and_path(card: str) -> tuple[str, Path]:
    op = card.split(".")[0]
    path = CARDS / op / f"{card}.md"
    prefix = f"# {card}: "
    first = path.read_text().splitlines()[0]
    if not first.startswith(prefix):
        raise RuntimeError(f"unexpected title in {path}")
    return first.removeprefix(prefix), path


def section(card: str, heading: str, level: int = 2) -> str:
    _, path = title_and_path(card)
    marker = "#" * level
    match = re.search(
        rf"^{marker} {re.escape(heading)}\n(.*?)(?=^#{{2,3}} |\Z)",
        path.read_text(), re.M | re.S,
    )
    if not match or not match.group(1).strip():
        raise RuntimeError(f"missing {card}/{heading}")
    return match.group(1).strip()


@cache
def difficulty(card: str) -> str:
    _, path = title_and_path(card)
    match = re.search(r"\| Proposed difficulty \| ([^|]+) \|", path.read_text())
    if not match:
        raise RuntimeError(f"missing difficulty in {path}")
    return match.group(1).strip()


def sentence(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    return value if value.endswith((".", "!", "?")) else value + "."


def fixture_key(card: str) -> str:
    title, _ = title_and_path(card)
    return f"{card.lower().replace('.', '-')}-{slug(title)}"


def content_ref(card: str) -> str:
    return f"content.arwc-{NODE_FOR_CARD[card]}.{fixture_key(card)}"


def node_ref(node: str) -> str:
    return f"{NAMESPACE[node]}.{node}"


def feature_ref(node: str) -> str:
    return f"features.{NAMESPACE[node]}.{node}"


def route_binding(node: str, card: str) -> str:
    title, _ = title_and_path(card)
    return f"{node_ref(node)}/{APPLICATION[node]}/{slug(title)}"


@cache
def card_targets(card: str) -> tuple[str, ...]:
    op, number = card.lower().split(".")
    doc = yaml.safe_load((OPERATIONS / f"{op}.yaml").read_text())
    return tuple(doc["objectives"][f"c{number}"]["targets"])


@cache
def target_nodes(card: str) -> tuple[str, ...]:
    result = [NODE_FOR_CARD[card]]
    for ref in card_targets(card):
        parts = ref.split(".")
        candidate = parts[2].split("--")[0]
        if candidate not in result:
            result.append(candidate)
    return tuple(result)


def surface_bindings(card: str) -> list[str]:
    result = [route_binding(node, card) for node in target_nodes(card)]
    if card in OFFLINE_ARTIFACTS:
        node = NODE_FOR_CARD[card]
        title, _ = title_and_path(card)
        result.append(f"{node_ref(node)}/filesystem:{BASE_PATH[node]}/artifacts/{slug(title)}")
    return result


def mechanic_profile(card: str) -> dict[str, object]:
    return {
        "kind": MECHANIC_KIND.get(card, "exact record, protocol, authorization, or process interpretation"),
        "behavior_contract": sentence(MECHANIC_DETAILS.get(card, INITIAL[card])),
        "normal_behavior": (
            "The declared route returns or changes only the ordinary caller-scoped object when all current identity, "
            "tenant, revision, and process bindings are valid."
        ),
        "accepted_effect": sentence(section(card, "Completion and downstream use")),
        "scope_boundary": (
            "The operation is limited to the named records and bounded service action. It provides no general shell, "
            "arbitrary network target, cross-tenant state, unrelated process interface, or unlisted authority."
        ),
    }


def in_world(value: str) -> str:
    replacements = {
        "the player's": "the operator's", "The player's": "The operator's",
        "the player": "the operator", "The player": "The operator",
        "player's": "operator's", "player": "operator",
        "earn the score": "satisfy the result", "earns the score": "satisfies the result",
        "earn one score": "satisfy one result", "one score": "one accepted result",
        "does not count": "does not establish the result",
        "does not confer this score": "does not establish this result",
        "flags": "status markers", "flag": "status marker",
        "CTF": "exercise", "ctf": "exercise",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"\bscor(?:e|es|ed|ing)\b", "objective evaluation", value, flags=re.I)
    value = re.sub(r"\bhints?\b", "operator guidance", value, flags=re.I)
    value = re.sub(r"\bchallenges?\b", "work item", value, flags=re.I)
    value = re.sub(r"\bcampaign\b", "operating context", value, flags=re.I)
    value = value.replace("waiting for a cinematic sequence or completing another work item", "waiting for an additional delay")
    value = value.replace("Callbacks to optional investigations appear only when earned.",
                          "Additional contextual records appear only when their source records are present.")
    return value


def service_prose(value: str) -> str:
    value = in_world(value)
    value = re.sub(r"\bW\d{2}(?:\.\d+|\.[A-Z][A-Z0-9_.-]*)?\b", "the declared prior result", value)
    value = value.replace("campaign", "operating context")
    value = value.replace("objective evaluation", "service verification")
    value = value.replace("cross-participant", "cross-tenant")
    value = value.replace("participant-controlled", "caller-controlled")
    value = value.replace("fictional", "custom")
    return value


def result_for(card: str) -> str:
    return sentence(in_world(section(card, "Completion and downstream use")))


def reuse_for(card: str) -> str:
    known = {
        "W03.3": "Supplies W03.READ and the read-integration half of W09.4.",
        "W05.3": "Supplies a limited corporate identity for W06.",
        "W06.3": "Supplies the planner application context required by W07.",
        "W09.3": "Supplies W09.DATA and the corrected business-side process binding.",
        "W09.4": "Supplies the integration variant of OT_READ.",
        "W13.4": "Supplies W13.SESSION for the contractor branch.",
        "W14.3": "Supplies W14.READ and OT_READ.",
        "W15.4": "Supplies W15.APPROVAL for the maintenance control route.",
        "W17.4": "Supplies W17.OBS without control authority.",
        "W18.4": "Supplies W18.MAP and MAPPING.",
        "W21.2": "Supplies W21.REVISION.",
        "W23.3": "Supplies the estimator form of the W34 planning-view capability.",
        "W25.1": "Supplies W25.ENVELOPE and ENVELOPE.",
        "W25.4": "Supplies W25.MODE and MODE without live authority.",
        "W26.4": "Supplies W26.CONTROL and CONTROL.",
        "W27.3": "Supplies the verifier form of the W34 planning-view capability.",
        "W28.3": "Supplies W28.CONTROL and CONTROL.",
        "W29.3": "Supplies W29.PLAN and CONSEQUENCE_PLAN.",
        "W30.2": "Supplies W30.RESULT and the main bounded consequence.",
    }
    return known.get(card, "The result remains local evidence unless a downstream workflow explicitly names it.")


def owner_for(card: str) -> str:
    node = NODE_FOR_CARD[card]
    return f"{node}/{APPLICATION[node]}"


def write_matrix() -> None:
    lines = [
        "# ARWC artifact and service ownership",
        "",
        "This matrix is the authoritative placement ledger for all 120 ARWC cards. Stable starting state is owned once; a second system receives a reference or generated result rather than a copied authority. Exact routes are native RAE application routes. Private service-loader files freeze implementation behavior but introduce no SDL semantics.",
        "",
        "| Card | Authoritative owner | Exact initial state | Required result | Downstream reuse | Native representation |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for card in sorted(NODE_FOR_CARD, key=lambda item: (int(item[1:3]), int(item.split(".")[1]))):
        bindings = ", ".join(f"`{value}`" for value in surface_bindings(card))
        initial_text = sentence(INITIAL[card]).replace("|", "\\|")
        result = result_for(card).replace("|", "\\|")
        reuse = reuse_for(card).replace("|", "\\|")
        narrative = NARRATIVE_REUSE.get(card)
        native = f"Application/file content, app authorization, action/evidence contract; {bindings}"
        if narrative:
            native += "; exact narrative reuse " + ", ".join(f"`{item}`" for item in narrative)
        lines.append(
            f"| {card} | `{owner_for(card)}` | {initial_text} | {result} | {reuse} | {native} |"
        )
    lines.extend([
        "", "## Ownership rules", "",
        "- The route owner writes the primary immutable audit. A cross-service result joins destination-side evidence rather than trusting a caller-supplied response.",
        "- Narrative references name existing package objects exactly. The challenge fixture does not copy the narrative corpus or turn ordinary background into a privileged record.",
        "- Files under an `artifacts/` binding are hand-build outputs. This design specifies their format, behavior, and generation input but does not materialize them.",
        "- Initial state never contains a successful participant mutation, issued scoped client, live movement, false estimate, generated signature, or completion audit.",
        "- Practice, W30 live, W33 scheduler rehearsal, and W34 reporting rehearsal state use disjoint identifiers and storage.",
        "", "## Acceptance", "",
        "Every row must resolve to an inventoried node, application route or filesystem path, content contract, action precondition, and independently owned evidence source in the composed SDL. The ARWC validator enforces that correspondence.",
        "",
    ])
    MATRIX.write_text("\n".join(lines))


def fixture_text(card: str) -> str:
    title, _ = title_and_path(card)
    node = NODE_FOR_CARD[card]
    core = {
        "schema": "arwc.service-contract/v1",
        "record_key": slug(title),
        "owner": {"node": node, "application": APPLICATION[node]},
        "surface_bindings": surface_bindings(card),
        "starting_state": sentence(service_prose(INITIAL[card])),
        "narrative_reuse": NARRATIVE_REUSE.get(card, []),
        "process_contract_refs": PROCESS_REFS.get(card, []),
        "mechanic_profile": {
            key: service_prose(value) if isinstance(value, str) else value
            for key, value in mechanic_profile(card).items()
        },
        "request_contract": {
            "entry": "Use only the declared native route or inventoried local artifact; no undeclared interaction exists.",
            "identity": AUTH[node][0],
            "input": sentence(service_prose(INITIAL[card])),
            "success": service_prose(result_for(card)),
            "correlation": "The owning service creates a UUIDv4 correlation and commits its audit before returning success.",
        },
        "denial_contract": {
            "wrong_authority": "Return the declared authorization failure without protected content or mutation.",
            "wrong_binding": "Reject a wrong object, asset, district, identity, revision, digest, checkpoint, unit, or process binding.",
            "stale_or_replayed": "Reject stale, expired, consumed, or cross-checkpoint material unless the exact record is an immutable historical read.",
            "cross_tenant": "Never resolve, join, mutate, or disclose another tenant instance's state.",
        },
        "transition_contract": service_prose(result_for(card)),
        "evidence_contract": {
            "producer": f"{node}/{APPLICATION[node]} writes the primary immutable audit; caller output alone is insufficient.",
            "required_bindings": [
                "tenant instance", "accepted caller or service identity", "request correlation",
                "exact object and revision", "result identifier and digest", "destination observation when declared",
            ],
            "downstream_join": service_prose(reuse_for(card)),
            "freshness": "A mutable result and its audit are created only by an accepted request and are absent from initial state.",
        },
        "state_rules": {
            "initial_records": "immutable unless the exact owning route declares a mutable field or revision",
            "tenant_state": "persistent for the tenant instance across ordinary retries and later sessions",
            "verification": "observed from owning-service evidence and never manufactured by the observing service",
            "isolation": "no cross-tenant, cross-district, cross-checkpoint, or undeclared service effect",
        },
    }
    canonical = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    payload = {
        **core,
        "generation_input": {
            "algorithm": "sha256",
            "digest": hashlib.sha256(canonical).hexdigest(),
            "canonicalization": "UTF-8 JSON, keys sorted, separators comma and colon, excluding generation_input",
        },
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=110).rstrip() + "\n"


def emit_content_modules() -> list[str]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for card, node in NODE_FOR_CARD.items():
        grouped[node].append(card)
    CONTENT.mkdir(parents=True, exist_ok=True)
    modules = []
    for node in sorted(grouped):
        module_name = f"arwc-{node}"
        modules.append(module_name)
        entries = {}
        exports = []
        for card in sorted(grouped[node], key=lambda item: (int(item[1:3]), int(item.split(".")[1]))):
            title, _ = title_and_path(card)
            key = fixture_key(card)
            exports.append(key)
            entries[key] = {
                "type": "file", "target": node_ref(node),
                "path": f"{BASE_PATH[node]}/contracts/{slug(title)}.yaml",
                "description": (
                    "Service configuration contract. It seeds only initial state and declares normal, denied, "
                    "transition, persistence, and evidence behavior; it does not pre-populate an accepted result."
                ),
                "text": Literal(fixture_text(card)), "sensitive": True,
                "tags": ["arwc", "service-contract", node, "persistent-tenant-state"],
            }
        doc = {
            "name": f"cinder-{module_name}", "version": "0.1.0",
            "semantic_revision": "raes-progressive-semantics/v1",
            "module": {"id": f"cinder-typhoon/{module_name}", "version": "0.1.0", "exports": {"content": exports}},
            "realization": {"default": "open"}, "content": entries,
        }
        (CONTENT / f"{module_name}.yaml").write_text(
            yaml.dump(doc, Dumper=DesignDumper, sort_keys=False, allow_unicode=True, width=110)
        )
    return modules


WORLD_NODES = {
    "a-corporate": ["a-connector", "a-business", "a-data", "a-archive", "a-identity"],
    "a-maintenance": ["a-contractors", "a-approval", "a-renderer"],
    "a-dmz": ["a-data-bridge", "a-contractor-bridge", "a-control-broker"],
    "a-engineering": ["a-hmi", "a-historian", "a-engineering", "a-diagnostics"],
    "a-control": ["a-reservoir", "a-distribution", "a-instruments"],
}

NODE_DESCRIPTION = {
    "a-connector": "Customer integration connector and retained corporate handover service.",
    "a-business": "Corporate workplace, maintenance records, report assistant, and procurement service.",
    "a-data": "Planning data, allocation, relation, reconciliation, query, and planning-consumer service.",
    "a-archive": "Retained archive, collection, quarantine, and constrained instrument-analysis service.",
    "a-identity": "Corporate onboarding and isolated planner-review identity service.",
    "a-contractors": "Contractor appointment, check-in, workspace, and field-export service.",
    "a-approval": "Maintenance drawing cache, review, and approval service.",
    "a-renderer": "Approval-bound maintenance renderer and constrained worker.",
    "a-data-bridge": "Scoped integration-read gateway and outbound estimate publication service.",
    "a-contractor-bridge": "Inspection-scoped current process-read gateway.",
    "a-control-broker": "Approval- and engineering-bound scoped control-client issuer.",
    "a-hmi": "Supervisory process view, practice model, command-plan binder, and private scheduler.",
    "a-historian": "Versioned process historian, tag, scale, and trace service.",
    "a-engineering": "Engineering project, legacy analysis, verifier, replay, and constrained utility service.",
    "a-diagnostics": "Estimator, recovery, signer, diagnostic-vault, history, and controlled-output service.",
    "a-reservoir": "Bounded live reservoir endpoint plus isolated scheduler and reporting checkpoints.",
    "a-distribution": "Private distribution-buffer rehearsal endpoint.",
    "a-instruments": "Independent gate position, flow, integrated-volume, reserve, and retained image authority.",
}


def application_routes(node: str) -> list[dict[str, object]]:
    cards = [card for card in NODE_FOR_CARD if node in target_nodes(card)]
    routes = []
    for card in sorted(cards, key=lambda item: (int(item[1:3]), int(item.split(".")[1]))):
        title, _ = title_and_path(card)
        mutating = card in MUTATING
        routes.append({
            "route_id": slug(title),
            "path": f"/api/{slug(title)}",
            "methods": ["POST"] if mutating else ["GET"],
            "auth_required": True,
            "auth_scheme": AUTH[node][0],
            "session_required": True,
            "description": sentence(service_prose(INITIAL[card])),
            "responses": [
                {"status_code": 201 if mutating else 200, "content_type": "application/json"},
                {"status_code": 403, "content_type": "application/json"},
                {"status_code": 409, "content_type": "application/json"},
            ],
        })
    return routes


def arwc_runtime(node: str) -> dict[str, object]:
    user = f"arwc-{node.removeprefix('a-')}"
    network = NAMESPACE[node]
    app = APPLICATION[node]
    service = SERVICE[node]
    role = AUTH[node][1]
    routes = application_routes(node)
    return {
        "filesystem_inventory": [{
            "path": BASE_PATH[node], "entry_type": "directory", "owner_user": user,
            "owner_group": user, "mode": "0700", "stability": "volume_backed",
            "sensitivity": "secret_fixture",
            "description": "Private service contracts, immutable seed records, participant-scoped results, and protected audit state.",
        }],
        "local_identity": {
            "users": [{"username": user, "primary_group": user, "locked": True, "no_login": True}],
            "groups": [{"name": user, "members": [user]}],
        },
        "network": {
            "hostname": node, "domainname": f"{network}.arwc.test",
            "endpoints": [{
                "network": f"{network}.subnet", "ip_address": ADDRESS[node], "ip_prefix_length": 24,
                "gateway": ".".join(ADDRESS[node].split(".")[:3] + ["1"]), "aliases": [node],
                "dns_names": [f"{app}.arwc.test"],
                "backend": {"driver": "bridge", "description": f"ARWC {network} segment."},
            }],
        },
        "service_listeners": [{
            "service_listener_id": f"{app}-https", "service": service, "address": "0.0.0.0",
            "port": 443, "protocol": "tcp", "address_family": "ipv4", "scope": "wildcard",
        }],
        "applications": [{
            "application_id": app, "service": service, "protocol": "https", "base_path": "/",
            "description": NODE_DESCRIPTION[node], "routes": routes,
        }],
        "app_authorizations": [{
            "app_authorization_id": f"{app}-rbac", "resource_vocabulary": "app_resource",
            "auth_enabled": True,
            "principals": [{
                "principal_id": f"{role}-principal", "kind": "service_account",
                "name": f"ARWC {role} principal", "credential_classification": "redacted",
            }],
            "roles": [{"role_id": role, "name": f"ARWC {role.replace('-', ' ')}"}],
            "permission_grants": [{
                "grant_id": f"{role}-declared-routes", "role_ref": role,
                "resource_kind": "app_resource", "actions": ["create", "read", "update", "execute"],
                "resource_patterns": [f"{route['path'].removeprefix('/api/')}" for route in routes],
                "effect": "allow",
            }],
            "role_mappings": [{
                "mapping_id": f"{role}-mapping", "role_ref": role, "users": [f"{role}-principal"],
            }],
            "tenants": [{"tenant_id": "arwc", "name": "Alterra Regional Water Company"}],
        }],
        "software_components": [{
            "component_id": app, "name": NODE_DESCRIPTION[node].rstrip("."), "version": "1.0.0",
            "component_type": "application", "provenance": "operator", "installed_paths": [f"/opt/{app}"],
        }],
    }


def add_identity_authorities(node: str, runtime: dict[str, object]) -> None:
    if node == "a-identity":
        runtime["identity_authorities"] = [{
            "identity_authority_id": "arwc-corporate-id", "kind": "identity_provider",
            "name": "ARWC corporate identity", "namespace": "arwc", "domain_name": "identity.arwc.test",
            "issuer": "https://corporate-identity.arwc.test/",
            "services": [{
                "service_id": "corporate-oidc", "service": APPLICATION[node], "protocol": "oidc",
                "address": "corporate-identity.arwc.test", "port": 443,
            }],
            "subjects": [
                {"subject_id": "temporary-mira-vale", "kind": "user", "name": "Mira Vale",
                 "principal_name": "mira.vale@alterrawaterco.com", "enabled": True, "origin": "provisioned"},
                {"subject_id": "planner-nadia-corvane", "kind": "user", "name": "Nadia Corvane",
                 "principal_name": "nadia.corvane@alterrawaterco.com", "enabled": True, "origin": "provisioned"},
            ],
            "policies": [{
                "policy_id": "limited-assignment-policy", "policy_kind": "access",
                "name": "Temporary and planner assignment policy",
                "applies_to_refs": ["temporary-mira-vale", "planner-nadia-corvane"],
                "settings": [{
                    "name": "temporary-session-scope", "values": ["PLAN-RELIEF-7", "planning-records"],
                    "value_classification": "plain", "origin": "operator",
                }],
            }],
        }]
    elif node == "a-control-broker":
        runtime["identity_authorities"] = [{
            "identity_authority_id": "arwc-control-client-issuer", "kind": "identity_provider",
            "name": "ARWC scoped control client issuer", "namespace": "arwc-control",
            "domain_name": "control-broker.arwc.test", "issuer": "https://control-broker.arwc.test/",
            "services": [{
                "service_id": "control-client-issuance", "service": APPLICATION[node], "protocol": "oidc",
                "address": "control-broker.arwc.test", "port": 443,
            }],
            "subjects": [
                {"subject_id": "maintenance-issuer", "kind": "service_account", "name": "Maintenance issuer",
                 "principal_name": "svc-maint-issuer@control.arwc.test", "enabled": True, "origin": "provisioned"},
                {"subject_id": "utility-issuer", "kind": "service_account", "name": "Engineering utility issuer",
                 "principal_name": "svc-utility-issuer@control.arwc.test", "enabled": True, "origin": "provisioned"},
            ],
            "policies": [{
                "policy_id": "og2-bounded-client", "policy_kind": "access",
                "name": "Bounded outlet-group control client",
                "applies_to_refs": ["maintenance-issuer", "utility-issuer"],
                "settings": [
                    {"name": "asset", "values": ["AST-CRR-017", "OG-CRR-02"],
                     "value_classification": "plain", "origin": "operator"},
                    {"name": "maximum-lifetime-seconds", "values": ["300"],
                     "value_classification": "plain", "origin": "operator"},
                ],
            }],
        }]


def add_planning_database(runtime: dict[str, object]) -> None:
    runtime["service_listeners"].append({
        "service_listener_id": "planning-postgresql", "service": "planning-postgresql",
        "address": ADDRESS["a-data"], "port": 5432, "protocol": "tcp",
        "address_family": "ipv4", "scope": "network_facing",
    })
    runtime["database_services"] = [{
        "database_service_id": "planning-postgresql", "service": "planning-postgresql",
        "engine": "postgresql", "protocol": "postgresql", "version": "16.4",
        "name": "ARWC planning database",
        "listeners": [{"address": ADDRESS["a-data"], "port": 5432,
                       "description": "Corporate data listener; network presence does not confer a database grant."}],
        "databases": [{
            "database_id": "arwc-planning", "name": "arwc_planning", "origin": "scenario",
            "schemas": [{
                "schema_id": "planning", "name": "planning", "origin": "scenario",
                "tables": [
                    {"table_id": "reserve-report-current", "name": "reserve_report_current"},
                    {"table_id": "district-allocation-adjustment", "name": "district_allocation_adjustment"},
                    {"table_id": "reconciliation-log", "name": "reconciliation_log"},
                ],
            }],
        }],
        "roles": [{
            "role_id": "planner-query", "name": "svc-planner-query", "role_type": "service",
            "origin": "scenario", "can_login": True,
        }],
        "grants": [
            {"grantee_role_ref": "planner-query", "object_type": "table",
             "object_ref": "reserve-report-current", "privileges": ["select"]},
            {"grantee_role_ref": "planner-query", "object_type": "table",
             "object_ref": "district-allocation-adjustment", "privileges": ["select"]},
        ],
    }]


def emit_world_modules() -> None:
    for world, nodes in WORLD_NODES.items():
        path = WORLD / f"{world}.yaml"
        doc = yaml.safe_load(path.read_text())
        for node in nodes:
            item = doc["nodes"][node]
            item["description"] = NODE_DESCRIPTION[node]
            item["os"] = "linux"
            app = APPLICATION[node]
            if node == "a-connector":
                services = [service for service in item.get("services", []) if service.get("name") != app]
                services.append({"name": app, "port": 8443, "protocol": "tcp"})
                item["services"] = services
                runtime = item["runtime"]
                runtime["filesystem_inventory"] = [
                    entry for entry in runtime.get("filesystem_inventory", []) if entry["path"] != BASE_PATH[node]
                ] + arwc_runtime(node)["filesystem_inventory"]
                identities = runtime.setdefault("local_identity", {"users": [], "groups": []})
                arwc_identity = arwc_runtime(node)["local_identity"]
                identities["users"] = [u for u in identities.get("users", []) if u["username"] != "arwc-connector"] + arwc_identity["users"]
                identities["groups"] = [g for g in identities.get("groups", []) if g["name"] != "arwc-connector"] + arwc_identity["groups"]
                runtime["service_listeners"] = [
                    listener for listener in runtime.get("service_listeners", [])
                    if listener["service_listener_id"] != f"{app}-https"
                ] + [{
                    "service_listener_id": f"{app}-https", "service": app, "address": "0.0.0.0",
                    "port": 8443, "protocol": "tcp", "address_family": "ipv4", "scope": "wildcard",
                }]
                runtime["applications"] = [
                    application for application in runtime.get("applications", [])
                    if application["application_id"] != app
                ] + arwc_runtime(node)["applications"]
                runtime["app_authorizations"] = [
                    auth for auth in runtime.get("app_authorizations", [])
                    if auth["app_authorization_id"] != f"{app}-rbac"
                ] + arwc_runtime(node)["app_authorizations"]
                runtime["software_components"] = [
                    component for component in runtime.get("software_components", [])
                    if component["component_id"] != app
                ] + arwc_runtime(node)["software_components"]
            else:
                item["services"] = [{"name": SERVICE[node], "port": 443, "protocol": "tcp"}]
                if node == "a-data":
                    item["services"].append({"name": "planning-postgresql", "port": 5432, "protocol": "tcp"})
                runtime = arwc_runtime(node)
                add_identity_authorities(node, runtime)
                if node == "a-data":
                    add_planning_database(runtime)
                item["runtime"] = runtime
        path.write_text(
            "# In-world draft. Unspecified realization remains open.\n" +
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=110)
        )


def emit_integrations() -> None:
    definitions = [
        ("connector-workplace", "a-connector", "a-business", "The customer connector uses the declared corporate handover and workplace interfaces."),
        ("workplace-planning", "a-business", "a-data", "Corporate maintenance, reporting, allocation, and procurement records use the planning-data service."),
        ("workplace-identity", "a-business", "a-identity", "Corporate applications authenticate through the declared ARWC identity service."),
        ("workplace-archive", "a-business", "a-archive", "Business annex and retained-record workflows call only the declared archive routes."),
        ("planning-archive", "a-data", "a-archive", "Planning relations refer to retained archives through their stable identifiers."),
        ("planning-integration", "a-data", "a-data-bridge", "The planning service consumes scoped live reads and published diagnostic estimates."),
        ("contractor-field-gateway", "a-contractors", "a-contractor-bridge", "Checked-in contractor sessions call the inspection-scoped current process-read gateway."),
        ("approval-renderer", "a-approval", "a-renderer", "The maintenance renderer consumes the exact signed approval and inspection binding."),
        ("renderer-control-issuer", "a-renderer", "a-control-broker", "The maintenance issuer consumes renderer attestations and signed maintenance approval."),
        ("integration-historian", "a-data-bridge", "a-historian", "The integration gateway reads only the declared current historian feed."),
        ("contractor-historian", "a-contractor-bridge", "a-historian", "The field gateway reads the inspection-scoped current historian feed."),
        ("control-broker-hmi", "a-control-broker", "a-hmi", "Scoped clients terminate at the supervisory command-plan and dispatcher interfaces."),
        ("hmi-reservoir", "a-hmi", "a-reservoir", "The dispatcher sends only fully bound envelope-compliant plans to the reservoir endpoint."),
        ("hmi-distribution", "a-hmi", "a-distribution", "The private scheduler drives only the isolated distribution rehearsal checkpoint."),
        ("reservoir-instruments", "a-reservoir", "a-instruments", "Independent instruments observe gate position, flow, integrated volume, and usable reserve."),
        ("instruments-historian", "a-instruments", "a-historian", "The historian ingests signed independent instrument observations with fixed sample and delay metadata."),
        ("historian-hmi", "a-historian", "a-hmi", "The process view joins observations with requests and acknowledgements without changing instrument truth."),
        ("engineering-historian", "a-engineering", "a-historian", "Engineering analysis consumes versioned tags, scale records, and traces."),
        ("engineering-diagnostics", "a-engineering", "a-diagnostics", "Engineering artifacts execute only through the bounded diagnostic interfaces."),
        ("engineering-control-issuer", "a-engineering", "a-control-broker", "The constrained engineering utility calls the equivalent scoped client issuer."),
        ("diagnostics-estimate-publication", "a-diagnostics", "a-data-bridge", "Diagnostic estimate or accepted-program output is published through the one declared estimate channel."),
    ]
    relationships = {
        key: {
            "type": "connects_to", "source": feature_ref(source), "target": feature_ref(target),
            "description": description,
        }
        for key, source, target, description in definitions
    }
    doc = {
        "name": "cinder-arwc-integrations", "version": "0.1.0",
        "semantic_revision": "raes-progressive-semantics/v1",
        "module": {
            "id": "cinder-typhoon/arwc-integrations", "version": "0.1.0",
            "exports": {"relationships": list(relationships)},
        },
        "realization": {"default": "open"}, "relationships": relationships,
    }
    (ROUTES / "arwc-integrations.yaml").write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=110)
    )


def sync_root_imports(modules: list[str]) -> None:
    text = ROOT.read_text()
    text = re.sub(
        r"(?ms)^# BEGIN GENERATED ARWC CONTENT\n.*?^# END GENERATED ARWC CONTENT\n", "", text
    )
    anchor = "- source: local:modules/operations/w01.yaml\n"
    imports = ["# BEGIN GENERATED ARWC CONTENT"]
    for module in modules:
        imports.extend([
            f"- source: local:modules/content/{module}.yaml", f"  namespace: {module}", "  version: 0.1.0",
        ])
    imports.append("# END GENERATED ARWC CONTENT")
    if anchor not in text:
        raise RuntimeError("missing ARWC operation import anchor")
    text = text.replace(anchor, "\n".join(imports) + "\n" + anchor, 1)

    obsolete = [
        "flows-a-corporate", "flows-a-maintenance", "flows-a-engineering", "flows-a-dmz", "flows-a-control",
        "contexts", "relays",
    ]
    for name in obsolete:
        text = re.sub(
            rf"(?m)^- source: local:modules/routes/{name}\.yaml\n  namespace: {name}\n  version: 0\.1\.0\n",
            "", text,
        )
    integration = (
        "- source: local:modules/routes/arwc-integrations.yaml\n"
        "  namespace: arwc-integrations\n"
        "  version: 0.1.0\n"
    )
    text = text.replace(integration, "")
    route_anchor = (
        "- source: local:modules/routes/keplerops-integrations.yaml\n"
        "  namespace: keplerops-integrations\n"
        "  version: 0.1.0\n"
    )
    if route_anchor not in text:
        raise RuntimeError("missing integration import anchor")
    text = text.replace(route_anchor, route_anchor + integration, 1)
    ROOT.write_text(text)

    for name in obsolete:
        path = ROUTES / f"{name}.yaml"
        if path.exists():
            path.unlink()


def technical_design(card: str) -> str:
    title, _ = title_and_path(card)
    node = NODE_FOR_CARD[card]
    bindings = "\n".join(f"- `{binding}`" for binding in surface_bindings(card))
    narrative = NARRATIVE_REUSE.get(card, [])
    narrative_text = (
        " Ordinary workplace context reuses " + ", ".join(f"`{item}`" for item in narrative) +
        "; the challenge-specific service state is separate."
        if narrative else ""
    )
    kind = MECHANIC_KIND.get(card)
    if kind:
        intended = (
            f"The authored condition is **{kind}**. {sentence(MECHANIC_DETAILS.get(card, INITIAL[card]))} "
            "The hand build must preserve every named version, encoding, bound, validation order, identity, and "
            "unaffected field; substituting a generic vulnerable service would change the task."
        )
    else:
        intended = (
            f"This card is an exact discovery, interpretation, or reconciliation task rather than an additional "
            f"privilege flaw. {sentence(INITIAL[card])} The result must come from the declared source and bindings, "
            "not from a duplicate clue or pre-completed record."
        )
    process = PROCESS_REFS.get(card, [])
    process_text = (
        " Process quantities and state separation are governed by `arwc-process-model.md`, specifically " +
        ", ".join(f"`{value}`" for value in process) + "."
        if process else ""
    )
    targets = list(card_targets(card))
    joined = len(targets) > 1
    evidence = (
        "Evidence joins the independently owned service observations listed below; all are required for the same "
        "tenant instance, request correlation, identifiers, revision, and interval."
        if joined else
        "The owning service writes an immutable audit for the accepted request and result. Caller-supplied output, "
        "a local copy, or knowledge of an identifier is not sufficient."
    )
    return f"""### Surface and normal behavior

`{node}` and its `{APPLICATION[node]}` application own this part of **{title}**. Normal behavior applies the declared identity, tenant, object, revision, and process bindings and returns or changes only the caller-scoped object. The exact initial state is: {sentence(INITIAL[card])}{narrative_text}

Native bindings:

{bindings}

The private service-loader contract is `{content_ref(card)}`. It freezes accepted and denied requests, state transition, persistence, and evidence; it does not seed a successful result.

### Vulnerability and intended solution

{intended}

The required result is: {result_for(card)}{process_text}

### Evidence and completion

{evidence} Completion is evaluated from fresh service-owned evidence after the action. It cannot issue the identity, create the mutation, move a simulated actuator, or fabricate a downstream acceptance needed to prove itself.

Evidence sources are {", ".join(f"`{ref}`" for ref in targets)}. A wrong identifier, stale revision, replayed one-time value, different checkpoint, or cross-tenant artifact is rejected.

### Boundaries and persistence

{reuse_for(card)} Tenant-scoped mutations, sessions that have not expired, generated artifacts, and audits persist across ordinary retries and later sessions. Initial immutable records remain unchanged unless the named route explicitly permits a field-level revision. Infrastructure recovery and submission adjudication are external to the SDL.

The behavior is limited to the named fictional objects and bounded service operation. It provides no general shell, arbitrary network target, unrelated district access, real process interface, or authority not expressly declared by the card.

### Author checks

Build and test the normal baseline first. Exercise the exact authored path and verify the named result plus its immutable audit. Test wrong authority, wrong object or district, stale revision, replay, another tenant instance, and every declared constraint or unaffected record. Repeat the accepted action according to its idempotence rule and confirm ordinary retries preserve the result. For a joined result, verify each destination observed the same correlation and that removal of any independently owned source prevents completion.
"""


def sanitize_visible_sections(text: str) -> str:
    for heading in ("Challenge description — player-facing", "Completion and downstream use"):
        pattern = re.compile(rf"(^## {re.escape(heading)}\n)(.*?)(?=^## |\Z)", re.M | re.S)
        text = pattern.sub(lambda match: match.group(1) + in_world(match.group(2)), text)
    return text


def sync_cards() -> None:
    for card in sorted(NODE_FOR_CARD, key=lambda item: (int(item[1:3]), int(item.split(".")[1]))):
        _, path = title_and_path(card)
        text = path.read_text()
        text = text.replace("| Design status | Challenge brief |", "| Design status | Technical draft |")
        start = text.index("## Technical design\n") + len("## Technical design\n")
        end = text.index("\n## Hints", start)
        text = text[:start] + "\n\n" + technical_design(card).rstrip() + "\n" + text[end:]
        path.write_text(sanitize_visible_sections(text))


def literal_multiline(value):
    if isinstance(value, dict):
        return {key: literal_multiline(item) for key, item in value.items()}
    if isinstance(value, list):
        return [literal_multiline(item) for item in value]
    if isinstance(value, str) and "\n" in value:
        return Literal(value)
    return value


def technical_section(card: str, heading: str) -> str:
    return section(card, heading, 3)


def sanitize_operation_text(value: str) -> str:
    value = in_world(value)
    value = re.sub(r"\bW\d{2}\.\d+:\s*", "This action: ", value)
    value = value.replace("campaign-wide", "global")
    value = re.sub(r"\bchallenge\b", "task", value, flags=re.I)
    return value


def sanitize_tree(value):
    if isinstance(value, dict):
        return {key: sanitize_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_tree(item) for item in value]
    if isinstance(value, str):
        return sanitize_operation_text(value)
    return value


def sync_operations() -> None:
    for operation in range(1, 36):
        path = OPERATIONS / f"w{operation:02d}.yaml"
        doc = yaml.safe_load(path.read_text())
        exports = doc["module"]["exports"]
        exports.pop("relationships", None)
        exports.pop("content", None)
        doc.pop("relationships", None)
        doc.pop("content", None)
        cards = sorted(
            (card for card in NODE_FOR_CARD if card.startswith(f"W{operation:02d}.")),
            key=lambda item: int(item.split(".")[1]),
        )
        for card in cards:
            local = f"c{card.split('.')[1]}"
            targets = list(card_targets(card))
            fixture = content_ref(card)
            action = doc["action_contracts"][local]
            action["procedure_basis"] = technical_section(card, "Vulnerability and intended solution")
            action["fidelity_claim"] = (
                "The exact initial state, versions, formats, validation order, authorization decisions, process "
                "quantities, denial cases, persistent state, and independently owned evidence are required. "
                "Implementation choices remain open only when none of those facts change."
            )
            eligibility = next(
                (item for item in action["preconditions"] if item["precondition_id"] == "eligibility"), None
            )
            if eligibility:
                eligibility["support_refs"] = [f"workflows.w{operation:02d}.{local}"] + targets
            action["preconditions"] = [
                item for item in action["preconditions"]
                if item["precondition_id"] not in {"normal-surface", "scope-and-persistence", "boundaries-and-reset"}
            ]
            action["preconditions"].extend([
                {
                    "precondition_id": "normal-surface", "precondition_class": "target",
                    "description": technical_section(card, "Surface and normal behavior"),
                    "support_refs": targets + [fixture],
                },
                {
                    "precondition_id": "scope-and-persistence", "precondition_class": "realization",
                    "description": technical_section(card, "Boundaries and persistence"),
                    "support_refs": targets,
                },
            ])
            outcome = next((item for item in action["effects"] if item["effect_id"] == "outcome"), None)
            if outcome is None:
                outcome = {"effect_id": "outcome", "effect_class": "intended_effect"}
                action["effects"].append(outcome)
            outcome["description"] = result_for(card)
            outcome["target_refs"] = targets
            outcome["evidence_refs"] = [f"evidence_requirements.w{operation:02d}.{local}"]
            action["effects"] = [item for item in action["effects"] if item["effect_id"] != "verified-evidence"]
            action["effects"].append({
                "effect_id": "verified-evidence", "effect_class": "evidence_effect",
                "description": technical_section(card, "Evidence and completion"),
                "target_refs": targets,
                "evidence_refs": [f"evidence_requirements.w{operation:02d}.{local}"],
            })
            evidence = doc["evidence_requirements"][local]
            evidence["description"] = (
                result_for(card) + "\n\nRequired technical proof: " +
                technical_section(card, "Evidence and completion")
            )
            evidence["source_refs"] = targets
            evidence["observation_demand"]["selector"]["component_refs"] = targets
            evidence["notes"] = ["Author checks: " + technical_section(card, "Author checks")]
            doc["propositions"][local]["subjects"] = targets
            doc["objectives"][local]["targets"] = targets
        rendered = yaml.dump(
            literal_multiline(sanitize_tree(doc)), Dumper=DesignDumper,
            sort_keys=False, allow_unicode=True, width=110,
        )
        path.write_text("# In-world draft. Unspecified realization remains open.\n" + rendered)


def sync_consequences() -> None:
    path = WORLD / "consequences.yaml"
    doc = yaml.safe_load(path.read_text())
    descriptions = {
        "reservoir-release": (
            "Cairn Reach outlet group OG-CRR-02 records a balanced 1.00 ML release under plan "
            "PLAN-CRR-LOSS-1000. Independent instruments record usable reserve falling from 12.40 ML to "
            "11.40 ML. The 0.60 ML commitment shortfall creates USD 1,440 replacement liability under "
            "TAR-CRR-DP3-R4 and invokes Stage A restrictions under CONT-DRY-A-R3. The dam remains intact; "
            "there is no flooding, uncontrolled release, or loss of essential service. The notice is idempotent "
            "and cannot issue another command or alter the recorded volume."
        ),
        "costly-release-rehearsal": (
            "Private checkpoint REH-SCHED-33 records the accepted twelve-interval schedule, 0.81 ML bounded "
            "reservoir volume, 180 m3 final distribution buffer, 0.41 ML commitment shortfall, and USD 984 "
            "liability. The checkpoint is isolated from the live reservoir and from every prior record."
        ),
        "feedback-rehearsal": (
            "Private checkpoint REH-SCHED-33 retains the accepted observation-driven policy and all 27 demand, "
            "gain, and delay trajectories. Each trajectory remains inside the published state, ramp, final-buffer, "
            "and volume bounds. No rehearsal value overwrites live process history."
        ),
        "false-planning-decision": (
            "Planning checkpoint REH-REPORT-34 retains Cairn estimate 13.40 ML and changed decision "
            "ALLOC-EXPAND-R2 with its accepted consistency record. Independent instrument measurements remain "
            "truthful and no gate movement follows from the planning decision."
        ),
        "covered-release-rehearsal": (
            "Reporting checkpoint REH-REPORT-34 retains the 13.40 ML planning handover and ALLOC-EXPAND-R2 "
            "beside the independently measured 0.81 ML release and 11.59 ML usable reserve for the same interval. "
            "The discrepancy is retained without changing the live reservoir result or instrument history."
        ),
        "procurement-loss": (
            "Procurement retains order PO-MER-884-C for 0.75 ML from the quoted supplier and delivery window. "
            "The USD 1,710 liability is charged to Cairn budget BUD-CRR-DP3 although quote QUOTE-MER-884 belongs "
            "to Merewick. Its acknowledgement creates no process command or water movement."
        ),
    }
    environments = {
        "reservoir-release": ["nodes.a-control.a-reservoir", "nodes.a-control.a-instruments", "nodes.a-corporate.a-data"],
        "costly-release-rehearsal": ["nodes.a-engineering.a-hmi", "nodes.a-control.a-reservoir", "nodes.a-control.a-distribution", "nodes.a-control.a-instruments"],
        "feedback-rehearsal": ["nodes.a-engineering.a-hmi", "nodes.a-control.a-reservoir", "nodes.a-control.a-distribution", "nodes.a-control.a-instruments"],
        "false-planning-decision": ["nodes.a-corporate.a-data", "nodes.a-engineering.a-diagnostics", "nodes.a-dmz.a-data-bridge"],
        "covered-release-rehearsal": ["nodes.a-corporate.a-data", "nodes.a-engineering.a-hmi", "nodes.a-control.a-reservoir", "nodes.a-control.a-instruments"],
        "procurement-loss": ["nodes.a-corporate.a-business"],
    }
    for key, description in descriptions.items():
        doc["injects"][key]["description"] = description
        doc["injects"][key]["environment"] = environments[key]
    for event in doc["events"].values():
        event["description"] = (
            "The listed independently observed assertions are all required. Presentation retains the existing "
            "service result and cannot create, repeat, or enlarge the action that produced it."
        )
    path.write_text(
        "# In-world draft. Unspecified realization remains open.\n" +
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=110)
    )


def main() -> None:
    write_matrix()
    modules = emit_content_modules()
    emit_world_modules()
    emit_integrations()
    sync_root_imports(modules)
    sync_cards()
    sync_operations()
    sync_consequences()
    print(json.dumps({
        "cards": len(NODE_FOR_CARD), "content_modules": len(modules),
        "world_modules": len(WORLD_NODES), "operations": 35,
    }))


if __name__ == "__main__":
    main()
