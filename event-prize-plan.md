# Event Prize Plan

Prepare 50 packs: one winner coin plus one $10 Starbucks card.

Tracking: [milestone #5](https://github.com/PaloAltoNetworks/shifter-scenarios/milestone/5). RAE SDL remains responsible only for per-participant objective/evidence truth. The operator-only prize policy is a separate sidecar; Shifter's native submissions, scoring, scheduler, communications, and claim state drive every award.

## RAE semantic findings

- Authored RAE SDL deliberately excludes scores, rewards, leaderboards, and evaluation results; those belong to the experiment/evaluator plane.
- SDL objectives, propositions, and assertions can define the evidence that completes one participant's challenge, but cannot choose winners across participant runs.
- Injects are authored world or narrative actions for a specific scenario occurrence. They do not provide ranking, drawings, one-prize enforcement, inventory, or claims.
- RAE shared time is scenario time, not the authoritative server receipt time needed to order solves from separate participant runs.
- RAE can represent derived scores outside SDL, but Shifter already has the authoritative CTF submissions, scoring, scheduler, and communications. Adding a second RAE scoring path would duplicate them.

Therefore the prize rules stay out of SDL and injects. A versioned operator-only policy sidecar defines the award slots and exact challenge membership; Shifter evaluates it and manages notification and claim.

| Qty | Award | Rule |
|---:|---|---|
| 10 | Overall leaders | Top 10 by total points; ties break by earliest time reaching the score. |
| 9 | Stage completion | First 3 to clear Training, KeplerOps, and ARWC. Unfilled places go to the highest stage scores. |
| 6 | Challenge bounties | First accepted solve of each bounty below. |
| 15 | Stage drawings | Draw 5 non-winners with at least one accepted solve in each stage. |
| 5 | Three-stage passport | Draw 5 non-winners with at least one solve in all three stages. |
| 5 | Good Citizen | Draw 5 valid peer nominees who helped without sharing answers. |

## Challenge bounties

- Training: `T03.4` and `T04.4`
- KeplerOps: `K09.4` and `K11.4`
- ARWC: `W30.2` and `W35.3`

## Rules

- One prize per person.
- Everyone in the overall top 10 is guaranteed a prize. If already awarded, pass that leaderboard pack to the next highest-ranked non-winner.
- Award bounties and complete stage clears from server-accepted solves. Run stage drawings at the three event-specific stage-close times; award everything else at the final ceremony.
- Move any unclaimed packs to a final drawing among non-winners with at least one accepted solve.
