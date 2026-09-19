# Challenge reference catalog

Research date: September 18, 2026. Updated for draft 3. This catalog records concrete precedents for
[the portfolio](operation-portfolio.md). These are organizer publications and
challenge-author materials. An original difficulty rating is evidence of the
source's intended tier, not a guarantee about its adaptation with the event's
provided agent. No source has been executed or timed during this design work.

**Selection rule:** hard, expert, and elite operations retain an identifiable
technical mechanism from a documented challenge. A reference is insufficient
if the adaptation retains only a category or an impressive title. Easy/medium
operations may use original accessible designs or published precedents.

Descriptions below are concise summaries. The portfolio supplies our proposed
fictional application. Public solutions may be used; participant familiarity is
legitimate. Preserve author/license notices if source or assets are reused.
A public writeup is not by itself a license to redistribute its entire bundle.
Pin the selected source revision when an adaptation enters implementation.

## C01

**Prison Pipeline: HTB Business CTF 2024.**
[Organizer README](https://github.com/hackthebox/business-ctf-2024/tree/main/misc/%5BMedium%5D%20Prison%20Pipeline)
and [official solution](https://raw.githubusercontent.com/hackthebox/business-ctf-2024/main/misc/%5BMedium%5D%20Prison%20Pipeline/official_writeup.md).

The README/index says **Medium**; the solution header says **Easy**. Record both.
The core is importer-assisted local file access, private registry credentials,
and execution when a consumer installs an altered dependency. K06/K26 retain
that chain. The proposed assisted entry route is medium, with an interface
example and clear customer binding. This is a particularly close narrative fit,
but only a fresh end-to-end solve can establish the route's actual difficulty.

## C02

**Chrono Mind: HTB Business CTF 2024, Easy.**
[Official solution](https://raw.githubusercontent.com/hackthebox/business-ctf-2024/main/misc/%5BEasy%5D%20Chrono%20Mind/official_writeup.md).

The original uses a small language model, unsafe context-file selection, and an
application that executes completed code. K21/K24 retain the application trust
failures, not a difficult model jailbreak. A small model in an old challenge
does not prove acceptable latency for 300 players; measure the chosen inference
setup. The context-file stage can provide a deterministic achievement even when
a generated answer is unreliable.

## C03

**Gloater: HTB Cyber Apocalypse 2024, Insane.**
[Author solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2024/main/pwn/%5BInsane%5D%20Gloater/README.md).

The source combines restricted pointer corruption, leaks, allocator metadata
control, and execution while blocking convenient targets. K04 adapts it to a
native support-bundle indexer, with hard/expert partial credit and elite
candidates for the difficult exploit transitions. Retain the constraints; a
plain writable function pointer would destroy the precedent. The original has
a probabilistic partial overwrite. Retry time is not difficulty: provide fast
isolated reset and measure attempts separately from reasoning time.

## C04

**Game Invitation: HTB Cyber Apocalypse 2024, Hard.**
[Official solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2024/main/forensics/%5BHard%5D%20Game%20Invitation/README.md).

The source requires payload carving from a document and successive script
reconstruction. K03 uses those mechanisms to recover an earlier Cinder
operation's configuration. The point is recovering something useful to the
intruder, not changing the participant's role to defender. The original author
already discusses AI-assisted code interpretation; do not presume its Hard
label survives unchanged.

## C05

**Percetron: HTB Cyber Apocalypse 2024, Hard.**
[Official solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2024/main/web/%5BHard%5D%20Percetron/README.md).

Its chain crosses request framing, server-side fetching, a database protocol,
certificate-derived query input, and an archive helper. K07, W04, and W11 draw
on different boundaries in this chain. Our hard/expert candidates must preserve
cross-component reasoning and the relevant constraints. A single generic SSRF
with an obvious internal URL does not inherit the full challenge's rating.
K07 keeps the request-framing problem; W11 keeps backend-protocol construction.
Their proofs must preserve that division instead of duplicating the same exploit.

## C06

**Tsayaki: HTB Cyber Apocalypse 2024, Hard.**
[Official solution](https://github.com/hackthebox/cyber-apocalypse-2024/tree/main/crypto/%5BHard%5D%20Tsayaki).

The source combines recovery of encryption context with TEA equivalent-key
behavior. K08 applies the mechanism to an explicitly obsolete entitlement
checker. Its hard allocations are candidates; identifying TEA and running a
known solver may now be quick. Do not add bulk arithmetic or repeat the same
oracle rounds merely to preserve a high rating.

## C07

**Metagaming: HTB Cyber Apocalypse 2024, Hard.**
[Author solution](https://github.com/hackthebox/cyber-apocalypse-2024/tree/main/reversing/%5BHard%5D%20Metagaming).

The source requires recovering a C++ template virtual machine and lifting its
constraints or reversing their arithmetic. K11 retains compile-time execution
semantics in FieldLink's policy compiler. Hard/expert work must require a model
of the actual program, not searching a source file for an embedded answer.

## C08

**apexsurvive: HTB Cyber Apocalypse 2024, Insane.**
[Official solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2024/main/web/%5BInsane%5D%20apexsurvive/official_writeup.md).

The source composes account-state ordering, browser-side leakage, privileged
browser actions, worker hijacking, and a renderer's server-side effect. K12
retains the long browser chain; W26 borrows the later renderer boundary in a
maintenance context. K12 has expert/elite candidates; the isolated W26 segment
is hard/expert, not automatically Insane. Browser version and timing constraints
must be reproducible without long bot queues or luck-based progress.

## C09

**Postviewer v3: Google CTF 2024 qualifiers.**
[Challenge-author writeup](https://github.com/google/google-ctf/blob/main/2024/quals/web-postviewer3/README.md).

The author records **19 solves and 303 points**, not a universal Hard/Elite label.
The key insight involves ambiguous input binding for isolated document origins,
with a delivery/race component. K10 borrows the boundary error. Proposed hard
work needs calibration; the original's solve count is context, not an assisted
solve-time forecast. The author also records an easier unintended path, which
belongs in our bypass review.

## C10

**University: HTB retired machine, Insane.**
[Official machine synopsis](https://www.hackthebox.com/machines/university).

K19/K20 adapt its certificate, delegated authentication, managed service, and
impersonation progression to supplier administration. Retain the need to combine
identities across boundaries. The retrieved official synopsis establishes the
rating and chain; it is **not a complete public author solution**. A follow-up
fetch redirected to HTB's general site, while indexed official content remained
available. Capture a stable authorized source and independently reproduce this
chain before committing K20's final elite allocation to production. K19's
partial chain is now medium/hard/expert, not separately elite. Do not infer
Windows directory realism or difficulty from an ATT&CK tag alone.

## C11

**SatelliteHijack: HTB Business CTF 2024, Hard.**
[Official solution](https://github.com/hackthebox/business-ctf-2024/tree/main/reversing/%5BHard%5D%20SatelliteHijack).

The source follows an indirect-function resolver into hooking and decoded
runtime code. K28 applies this to an archived connector with environment-specific
diagnostics. Retain the discrepancy between superficial analysis and actual
loaded behavior. This is a supplier product clue, not a second arbitrary
malware specimen disconnected from the campaign.

## C12

**Flash-ing Logs: HTB Cyber Apocalypse 2024, Hard.**
[Official solution](https://github.com/hackthebox/cyber-apocalypse-2024/tree/main/hw/Flash-ing%20Logs%20%5BHard%5D).

The original joins source analysis, a flash datasheet, record checks, and
selective changes that preserve other data. W20 adapts this to a retained
maintenance image and simulated device interface. The hard work is reasoning
about storage semantics and valid records, not physical equipment access or
memorizing a vendor command. A file edited without those constraints would be
a different, easier challenge.

## C13

**Kalman At Me Bro: Hack-a-Sat 4 qualifier, 2023, relative difficulty 5/5.**
[Organizer description](https://raw.githubusercontent.com/cromulencellc/hackasat-qualifier-2023/main/challenges/3_Pure_Pwnage/5_Kalman_At_Me_Bro/readme.md)
and [solver explanation](https://github.com/cromulencellc/hackasat-qualifier-2023/tree/main/challenges/3_Pure_Pwnage/5_Kalman_At_Me_Bro/solver).

The difficult mechanism is a measurement-list memory lifecycle flaw and
allocator manipulation, used to influence estimator state. It is not evidence
that difficult Kalman-filter mathematics alone makes a good CTF. W23 retains
memory exploitation and controlled state corruption in an isolated planning
estimator whose output can feed W34's in-story report. The live reservoir evaluator must use independent truth. This is an
elite candidate with a concrete published mechanism, not a direct reproduction
of satellite physics in a water plant.

## C14

**Spectrel Imaging: Hack-a-Sat 4 qualifier, 2023, relative difficulty 5/5.**
[Organizer description](https://raw.githubusercontent.com/cromulencellc/hackasat-qualifier-2023/main/challenges/3_Pure_Pwnage/4_Spectrel_Imaging/README.md),
[experiment generator](https://raw.githubusercontent.com/cromulencellc/hackasat-qualifier-2023/main/challenges/3_Pure_Pwnage/4_Spectrel_Imaging/solver/genSequence.py),
and [measurement analysis](https://raw.githubusercontent.com/cromulencellc/hackasat-qualifier-2023/main/challenges/3_Pure_Pwnage/4_Spectrel_Imaging/solver/evaluate.py).

The source builds repeated sequencer experiments and extracts protected data
from timing measurements. W16 retains experimental design and signal recovery
in a diagnostic instrument. This is an elite candidate with a significant
hosting-fairness risk. The source explicitly uses asynchronous execution. Pilot
noise, latency, and per-player measurement isolation before accepting it. A
simple pre-labeled trace must not inherit the original difficulty.

## C15

**ROT128: HTB Cyber Apocalypse 2024, Insane.**
[Official solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2024/main/crypto/%5BInsane%5D%20ROT128/README.md).

The source models a custom linear hash to construct collisions. W27 applies the
same algebraic weakness to a legacy engineering-program integrity check, then
requires a meaningful accepted program. Keep the defect explicitly in that
custom component. The adaptation does not imply that modern cryptographic
signatures are breakable. Elite candidacy depends on retaining substantive
model construction and acceptance constraints after public-solver assistance.

## C16

**Maze of Mist: HTB Cyber Apocalypse 2024, Hard.**
[Author solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2024/main/pwn/%5BHard%5D%20Maze%20of%20Mist/README.md).

The source exploits a tiny executable with few convenient instructions, using
its environment's virtual shared object and preserving the needed privilege.
W28 retains those constraints in an engineering utility. This supports a hard
control-authority route, not a claim of elite kernel exploitation. Pin the
execution environment and provide debugging material; accidental environment
mismatch is not a useful obstacle.

## C17

**Confinement: HTB Cyber Apocalypse 2024, Hard.**
[Official solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2024/main/forensics/%5BHard%5D%20Confinement/README.md).

The source recovers a quarantined program and reconstructs its data encryption.
W12 adapts recovery and cryptographic analysis to an old collector/archive.
It provides an intelligence payoff and alternate data access. Ransomware
execution and catastrophic consequences are not part of the adaptation.

## C18

**SOS or SSO?: HTB Business CTF 2024, Hard.**
[Official solution](https://github.com/hackthebox/business-ctf-2024/tree/main/web/%5BHard%5D%20SOS%20or%20SSO%3F).

The source crosses client-side note processing, identity-provider configuration,
and a backend query assumption. K18 retains the application-to-identity-to-data
composition. The participant must understand how one trusted output becomes
another component's input; merely finding a weak password would not preserve
the source's insight or difficulty.

## C19

**Aurors Archive: HTB Cyber Apocalypse 2025, Hard.**
[Official solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2025/main/web/web_aurorus_archive/README.md).

The source composes OAuth state confusion, client rendering, cookie behavior,
and execution through an apparently restricted database interface. W06 retains
the browser/session problem; W07 retains the separate database boundary. Test
these as successive substantive achievements. Source-tier inheritance does
not justify counting ordinary application navigation as hard work.

## C20

**Tales for the Brave: HTB Cyber Apocalypse 2025.**
[Official solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2025/main/forensics/Tales%20for%20the%20Brave/README.md)
and [organizer index](https://github.com/hackthebox/cyber-apocalypse-2025).

The index assigns four stars, but the writeup calls it **Medium**. W08 is a
medium/hard candidate, with this discrepancy retained. It draws on script and
messaging reconstruction followed by dynamic analysis of compiled code.
Represent the messaging artifacts locally; require no real Telegram account.
If the provided agent handles the whole reconstruction routinely, reduce the
hard allocations and replace the lost depth elsewhere.

## C21

**Gateway: HTB Cyber Apocalypse 2025, Hard.**
[Official solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2025/main/reversing/%5BHard%5D%20Gateway/README.md).

The source hides behavior across 32-bit and 64-bit execution modes. W19 uses
that analysis problem in an old engineering diagnostic. This replaces the
second indirect-function-loader puzzle and gives players a different reason
to distrust initial decompiler output. K28's product history can help locate
it without giving away the mode-switching solution.

## C22

**Vault: HTB Cyber Apocalypse 2025, Hard.**
[Official solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2025/main/pwn/%5BHard%5D%20Vault/README.md).

The source combines formatting-length misuse with a parser boundary error to
control execution despite a stack canary. W31 adapts this to a diagnostic
service. Its proposed expert steps require preserving the interacting
constraints; the original Hard rating does not automatically establish Expert.
This offers different native exploitation from the heap-heavy elite branches.

## C23

**Twin Oracles: HTB Cyber Apocalypse 2025, Hard.**
[Official solution](https://raw.githubusercontent.com/hackthebox/cyber-apocalypse-2025/main/crypto/Twin%20Oracles/README.md).

The source combines prediction of a weak random selector with interpretation
of different RSA oracle responses under a query bound. W24.1–W24.3 place this in
a legacy recovery interface whose recovered value opens the diagnostic evidence
bundle. W24.4 uses a separate precedent, C32, for signing authority. Retain the need to distinguish response semantics;
replace the previous duplicate TEA problem. Query limits must support the
intended solution comfortably and must not depend on public network latency.

## C24

**OmniWatch: HTB Business CTF 2024.**
[Official solution](https://raw.githubusercontent.com/hackthebox/business-ctf-2024/main/web/%5BMedium%5D%20OmniWatch/README.md).

The directory says Medium; the solution says **Hard** and the index gives four
stars. Its mechanism combines header injection, cache poisoning, and downstream
token checks. W15 uses that chain in the project-viewing workflow, replacing a
second Postviewer adaptation. Preserve informative cache behavior and a fair
reproducer for the race. Rate the whole adaptation with assistance, rather than
selecting whichever original label best fits a desired allocation.

## C25

**Heart Protector: HTB Cyber Apocalypse 2025, Hard.**
[Official solution](https://github.com/hackthebox/cyber-apocalypse-2025/tree/main/reversing/%5BHard%5D%20Heart%20Protector).

The source uses a Nim executable with an embedded virtual machine whose program
produces a decryption key. W22.1–W22.3 retain runtime emulation and protected
artifact recovery in the engineering project viewer. The key, readable project,
and engineering decision complete W22.3 together. W22.4 uses C31 for a separate
review-helper investigation. K11's compile-time constraint
lifting is different work, though both benefit from learning to model a VM.
Difficulty must reflect that transfer for someone who solves both.

## C26

**FlecksOfGold: HTB Cyber Apocalypse 2024, Hard.**
[Official solution](https://github.com/hackthebox/cyber-apocalypse-2024/tree/main/reversing/%5BHard%5D%20FlecksOfGold).

The source requires reconstructing a C++ entity/component system and either
patching behavior or recovering its result through analysis. W32 uses the same
structural reasoning in an offline process-replay artifact. It replaces a
second flash-edit operation. Preserve the relation between components, update
systems, and observed behavior; do not add an unrelated game maze.

## What this evidence does and does not establish

The portfolio now has named lineage for every hard-and-above operation, including
published Insane and 5/5 mechanisms for its elite candidates. That meets the
selection rule at architecture stage. It does not establish that the resulting
milestones deserve their assigned tiers, that every source asset is reusable,
or that the event has enough hours of genuinely difficult play.

The catalog deliberately records inconsistent ratings, an advanced competition
source without an explicit tier, and a machine for which only the official
synopsis was available. Resolve these through source capture and prototype
solves. Do not silently upgrade weak evidence into a tested difficulty claim.


## C27

**PipeDream: HTB Business CTF 2025, Hard.**
[Official solution](https://raw.githubusercontent.com/hackthebox/business-ctf-2025/master/cloud/PipeDream/README.md).

The chain joins cloud-held credentials, repository history, build control, and
signed deployment. K29 retains those connected trust boundaries. Its final
release-rollover constraint is an authored extension, not a source feature or
an inherited Expert rating. Preserve meaningful work across the boundaries;
a found key followed by an automatic deployment is insufficient.

## C28

**codebuild_secrets: CloudGoat, Hard challenge lab.**
[Publisher scenario](https://raw.githubusercontent.com/RhinoSecurityLabs/cloudgoat/master/cloudgoat/scenarios/aws/codebuild_secrets/README.md)
and [snapshot-route walkthrough](https://raw.githubusercontent.com/RhinoSecurityLabs/cloudgoat/master/cloudgoat/scenarios/aws/codebuild_secrets/cheat_sheet_calrissian.md).

K30 retains the discrepancy between backup/restore authority and direct data
access. Restoration and access to the recovered records form one hard candidate.
The customer-history reconciliation is our medium story join. This is a known
rated security challenge, not evidence from a timed CTF leaderboard.

## C29

**ecs_efs_attack: CloudGoat, Hard challenge lab.**
[Publisher scenario](https://raw.githubusercontent.com/RhinoSecurityLabs/cloudgoat/master/cloudgoat/scenarios/aws/ecs_efs_attack/README.md)
and [walkthrough](https://raw.githubusercontent.com/RhinoSecurityLabs/cloudgoat/master/cloudgoat/scenarios/aws/ecs_efs_attack/cheat_sheet.md).

K31 retains workload modification, runtime identity, a mutable resource-label
condition, and protected data access. The useful insight is their composition.
The source's provider-specific services explain the mechanism; they do not
select Cinder's topology. A simulation must preserve actual permission and
identity evaluation, rather than accepting a scripted sequence of API names.

## C30

**Terraforming Mars: Hack-a-Sat 4 qualifier, 2023, relative difficulty 4/5.**
[Organizer description](https://raw.githubusercontent.com/cromulencellc/hackasat-qualifier-2023/main/challenges/1_Aerocapture_The_Flag/2_Teraforming_Mars/README.md),
[challenge evaluator](https://raw.githubusercontent.com/cromulencellc/hackasat-qualifier-2023/main/challenges/1_Aerocapture_The_Flag/2_Teraforming_Mars/challenge/challenge.py),
and [submission driver](https://raw.githubusercontent.com/cromulencellc/hackasat-qualifier-2023/main/challenges/1_Aerocapture_The_Flag/2_Teraforming_Mars/solver/solver.py).

The original evaluates timed maneuvers against a simulated trajectory, an input
budget, ordering, and physical/contact constraints. W33 retains constrained
control planning and independent trajectory evaluation, replacing the domain
model with bounded water allocation. Scheduler abuse and changing-case feedback
are authored additions. The submission driver reads a prepared solution; it is
not proof that an agent can discover a solution cheaply. No orbital machinery,
source catastrophe, or 5/5 elite rating transfers to the adaptation.

## C31

**Oblique Final: HTB Cyber Apocalypse 2024, Insane.**
[Official writeup](https://github.com/hackthebox/cyber-apocalypse-2024/tree/main/forensics/%5BInsane%5D%20Oblique%20Final).

The header and directory rate it Insane; the synopsis calls it a hard forensic
challenge. Its relevant mechanism is ReadyToRun stomping: observed execution
contradicts the managed representation, and native-code analysis reveals a
concealed user. W22.4 retains that evidence/representation conflict and identity
recovery in a commissioning review helper. The recovered identity's archive
access is the campaign payoff; Heart Protector supplies none of this analysis.

The adaptation supplies a bounded commissioning capture and the retained helper,
rather than making large hibernation-image conversion a prerequisite. Preserve
the work of establishing which behavior actually ran and recovering its usable
identity. The proposed Expert rating reflects this narrower problem; it does
not inherit Insane from the full forensic source. The archive is historical,
with no implied current control rights.

## C32

**Curveware: HTB Business CTF 2025, Hard.**
[Official writeup](https://raw.githubusercontent.com/hackthebox/business-ctf-2025/master/crypto/Curveware/README.md).

The source joins executable analysis, a custom elliptic-curve signature scheme,
partial nonce information in file metadata, and mathematical key recovery.
W24.4 retains that combined problem in a diagnostic signer and its signed
records. The participant must derive the scheme and relevant record relations;
W24.3 supplies the evidence bundle, not those results or the signing key.

Fresh authorization for a scoped diagnostic export replaces the source's
encrypted-file recovery. Its ransomware behavior and file-encryption key reuse
are not part of the campaign. Retain the useful metadata and adequate finite
evidence instead of inflating sample collection or forcing brute force. Expert
is proposed for the whole binary/cryptographic composition, including accepted
authorization, with no separate scores for recovering and then using a key.
