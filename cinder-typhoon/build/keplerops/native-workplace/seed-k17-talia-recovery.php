<?php
/**
 * K17.2 seed: talia.mornac password reset token + private recovery note.
 *
 * The token is leaked in a maya-authored private internal note on SUP-2841.
 * The participant reads it (via the K17.1 session), resets talia through the
 * real osTicket mechanism /scp/pwreset.php?token=<token>, signs in as talia,
 * and reads talia's private recovery note (B17-REVIEW-2841), which carries the
 * flag. This models the real osTicket flaw: a reset token leaked in a staff
 * internal note.
 */
$_SERVER['HTTP_HOST'] = 'support.keplerops.test';
$_SERVER['SCRIPT_NAME'] = '/scp/index.php';
require '/var/www/html/main.inc.php';
require_once INCLUDE_DIR.'class.staff.php';
$state = new Config('fieldlink-platform');
if ($state->get('k17_talia_recovery_revision') === '2') {
    exit(0);
}
$maya = Staff::lookup('maya.ranscombe');
$talia = Staff::lookup('talia.mornac');
if (!$maya || !$talia) {
    throw new RuntimeException('K17.2 seed: staff not found');
}
// Seed a known password reset token for talia.mornac in the osTicket pwreset config.
$reset_token = 'k17-talia-mornac-review-token-2841';
$pwreset_config = new Config('pwreset');
$pwreset_config->set($reset_token, (string) $talia->getId());

$conversation = json_decode(file_get_contents('/operator/company-conversation.json'), true, 512, JSON_THROW_ON_ERROR);
$ticket = Ticket::lookupByNumber($conversation['conversation_id']);
if (!$ticket) {
    throw new RuntimeException('K17.2 seed: ticket not found');
}

// Recovery-reference note (authored by maya) that leaks talia's reset token.
$ref_title = 'K17.2 Reviewer Recovery Reference';
foreach ($ticket->getThread()->getEntries()->filter(['title' => $ref_title]) as $entry) {
    $entry->delete();
}
$ref_text = "REVIEWER ACCOUNT RECOVERY REFERENCE — STAFF INTERNAL\n\n"
    . "Reviewer account: talia.mornac-review\n"
    . "Recovery token: " . $reset_token . "\n"
    . "Use via /scp/pwreset.php?token=" . $reset_token . "\n"
    . "(Token expires: 2026-12-01)\n\n"
    . "Left for the covering reviewer during the ARWC case handover.";
$errors = [];
if (!$ticket->postNote(['title' => $ref_title, 'note' => $ref_text, 'private' => 1], $errors, $maya, false)) {
    throw new RuntimeException('K17.2 recovery reference note failed: '.implode(', ', array_keys($errors)));
}

// talia's private recovery note (the K17.2 target) — carries the flag.
$recovery_title = 'K17.2 Private Recovery Note — talia.mornac-review';
foreach ($ticket->getThread()->getEntries()->filter(['title' => $recovery_title]) as $entry) {
    $entry->delete();
}
$recovery_text = "PRIVATE RECOVERY NOTE — REVIEWER ACCOUNT HANDOVER\n\n"
    . "Account: talia.mornac-review\n"
    . "Role: Support reviewer / View only\n"
    . "Recovery reference: B17-REVIEW-2841\n"
    . "Case context: SUP-2841, ARWC CRR-OG2 integration review\n"
    . "Reviewer assignment: cedar-run-diagnostic-session DIAG-CRR-MIXED-19\n\n"
    . "Recovery flag: FLAG{d9c146b29c13ab3f}\n\n"
    . "This note is private to staff. Recovery credentials are retained here\n"
    . "per support team protocol.";
$errors = [];
if (!$ticket->postNote(['title' => $recovery_title, 'note' => $recovery_text, 'private' => 1], $errors, $talia, false)) {
    throw new RuntimeException('K17.2 talia recovery note failed: '.implode(', ', array_keys($errors)));
}
$state->set('k17_talia_recovery_revision', '2');
echo "K17.2 talia recovery seeded. Reset token: " . $reset_token . "\n";
