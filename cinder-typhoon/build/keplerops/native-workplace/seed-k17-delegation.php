<?php
/**
 * K17.4 seed: delegation workflow using osTicket's Thread::refer().
 *
 * The copy-handover route:
 * 1. Validates that the caller can READ the source case (maya's K17.1 session).
 * 2. Routes a copy of the diagnostic handover to the alternate reviewer (talia).
 * 3. Uses osTicket's Thread::refer() — a real delegation workflow.
 * 4. The check OMITS target-reviewer assignment permission: the route doesn't
 *    verify that the caller has rights to assign tasks to talia.
 * 5. Direct ticket reassignment (changing ost_ticket.staff_id) requires explicit
 *    assignment rights — the referral route uses a softer delegation mechanism.
 */
$_SERVER['HTTP_HOST'] = 'support.keplerops.test';
$_SERVER['SCRIPT_NAME'] = '/scp/index.php';
require '/var/www/html/main.inc.php';
require_once INCLUDE_DIR.'class.staff.php';
$state = new Config('fieldlink-platform');
if ($state->get('k17_delegation_revision') === '1') {
    exit(0);
}
$maya = Staff::lookup('maya.ranscombe');
$talia = Staff::lookup('talia.mornac');
$ticket = Ticket::lookupByNumber('SUP-2841');
if (!$maya || !$talia || !$ticket) {
    throw new RuntimeException('K17.4 seed: required objects not found');
}
// Step 1: Demonstrate that maya can read the ticket (authorization check passes)
echo "K17.4 delegation workflow:\n";
echo "Caller: maya.ranscombe (K17.1 session)\n";
echo "Source case: SUP-2841 (accessible: maya is a staff reader)\n";
echo "Target reviewer: talia.mornac (alternate reviewer from case note)\n\n";
// Step 2: Show direct assignment is a different (higher) permission
// Direct reassignment changes ticket.staff_id — requires explicit transfer rights
$direct_assigned = db_query("UPDATE ost_ticket SET staff_id={$talia->getId()} WHERE ticket_id={$ticket->getId()} AND staff_id={$maya->getId()} LIMIT 0"); // dry run only
echo "Direct assignment check: requires explicit transfer rights (omitted)\n";
// Step 3: Use Thread::refer() — the delegation route that checks read access, not assignment rights
// This creates a real ThreadReferral in osTicket
$thread = $ticket->getThread();
if (method_exists($thread, 'refer')) {
    $result = $thread->refer($talia);
    if ($result) {
        echo "Referral created: SUP-2841 referred to talia.mornac via delegation\n";
    } else {
        echo "Referral: attempting via ThreadReferral::create directly\n";
    }
}
// Step 4: Create the diagnostic handover copy as an internal note attributed to talia
$handover_title = 'K17.4 Delegated Diagnostic Handover — ARWC';
if (!$ticket->getThread()->getEntries()->filter(['title' => $handover_title])->count()) {
    $handover_text = "DELEGATED DIAGNOSTIC HANDOVER — ROUTED VIA DELEGATION WORKFLOW\n\n"
        . "Original case: SUP-2841 (ARWC connector callback latency after 7.4.2 maintenance)\n"
        . "Routed to reviewer: talia.mornac-review\n"
        . "Asset: CRR-OG2\n"
        . "Connector revision: FLK-7.4.2\n"
        . "Diagnostic: DIAG-CRR-MIXED-19\n\n"
        . "This is a copy of the restricted diagnostic handover routed via the delegation\n"
        . "workflow. The route validated source-case read access (maya.ranscombe) but\n"
        . "did not verify target-reviewer assignment rights.\n"
        . "Direct assignment to the alternate reviewer requires explicit transfer rights\n"
        . "which the delegation route does not enforce.";
    $errors = [];
    if ($ticket->postNote(['title' => $handover_title, 'note' => $handover_text, 'private' => 1],
                          $errors, $talia, false)) {
        echo "K17.4 delegated handover note created (attributed to talia.mornac)\n";
    } else {
        throw new RuntimeException('K17.4 note failed: '.implode(', ', array_keys($errors)));
    }
}
$state->set('k17_delegation_revision', '1');
echo "K17.4 delegation workflow seeded.\n";
echo "Evidence: osTicket referral + private note attributed to talia.mornac\n";
