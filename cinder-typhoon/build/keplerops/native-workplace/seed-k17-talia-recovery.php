<?php
/**
 * K17.2 seed: seed talia.mornac's password reset token and private recovery note.
 *
 * The reset token is exposed in the K17.1 handover note (the "case fragment").
 * When the participant reads maya's K17.1 note, they find talia's reset token.
 * They visit /scp/pwreset.php?token=<token> to reset talia's password.
 * After login, they read talia's private recovery note.
 *
 * This is a real osTicket flaw: leaked reset token via staff internal note.
 */
$_SERVER['HTTP_HOST'] = 'support.keplerops.test';
$_SERVER['SCRIPT_NAME'] = '/scp/index.php';
require '/var/www/html/main.inc.php';
require_once INCLUDE_DIR.'class.staff.php';
$state = new Config('fieldlink-platform');
if ($state->get('k17_talia_recovery_revision') === '1') {
    exit(0);
}
$maya = Staff::lookup('maya.ranscombe');
$talia = Staff::lookup('talia.mornac');
if (!$maya || !$talia) {
    throw new RuntimeException('K17 seed: staff not found');
}
// Seed a known password reset token for talia.mornac in the osTicket pwreset config.
// This token would normally be emailed — here it's exposed in the handover note.
$reset_token = 'k17-talia-mornac-review-token-2841';
$pwreset_config = new Config('pwreset');
$pwreset_config->set($reset_token, (string) $talia->getId());
// Update the K17.1 handover note to include talia's reset token (case fragment leak).
$conversation = json_decode(file_get_contents('/operator/company-conversation.json'), true, 512, JSON_THROW_ON_ERROR);
$ticket = Ticket::lookupByNumber($conversation['conversation_id']);
$handover_title = 'K17 Private Handover — ARWC Case Transition';
$entries = $ticket->getThread()->getEntries()->filter(['title' => $handover_title]);
if ($entries->count() === 0) {
    throw new RuntimeException('K17 handover note not found');
}
// The existing note already has the handover. We update it to include talia's reset token.
// Delete existing and re-create with the token included.
foreach ($entries as $entry) {
    // Add the recovery token to the existing note text
    $existing_text = $entry->getBody()->getClean();
    if (strpos($existing_text, 'talia.mornac') === false) {
        // Update not needed — seed the update text
        $recovery_fragment = "\n\nRecovery token for reviewer account talia.mornac-review:\nreset-ref: ".$reset_token."\nUse via /scp/pwreset.php?token=".$reset_token."\n(Token expires: 2026-12-01)";
        // Note: osTicket thread entries are immutable after creation.
        // Create a follow-up note with the recovery fragment.
        $errors = [];
        if (!$ticket->postNote(['title' => 'K17.2 Reviewer Recovery Reference',
                                'note' => $recovery_fragment, 'private' => 1],
                               $errors, $maya, false)) {
            throw new RuntimeException('K17.2 recovery note failed: '.implode(', ', array_keys($errors)));
        }
    }
}
// Add talia's private recovery note (the K17.2 target)
$recovery_title = 'K17.2 Private Recovery Note — talia.mornac-review';
$existing_recovery = $ticket->getThread()->getEntries()->filter(['title' => $recovery_title]);
if (!$existing_recovery->count()) {
    $recovery_text = "PRIVATE RECOVERY NOTE — REVIEWER ACCOUNT HANDOVER\n\n"
        . "Account: talia.mornac-review\n"
        . "Role: Support reviewer / View only\n"
        . "Recovery reference: B17-REVIEW-2841\n"
        . "Case context: SUP-2841, ARWC CRR-OG2 integration review\n"
        . "Reviewer assignment: cedar-run-diagnostic-session DIAG-CRR-MIXED-19\n\n"
        . "This note is private to staff. The reviewer account was established\n"
        . "during the ARWC case review. Recovery credentials are retained here\n"
        . "per support team protocol.";
    $errors = [];
    if (!$ticket->postNote(['title' => $recovery_title, 'note' => $recovery_text, 'private' => 1],
                           $errors, $talia, false)) {
        throw new RuntimeException('K17.2 talia recovery note failed: '.implode(', ', array_keys($errors)));
    }
}
$state->set('k17_talia_recovery_revision', '1');
echo "K17.2 talia recovery seeded. Reset token: ".$reset_token."\n";
