<?php
/**
 * K17.3 seed: ARWC organization in osTicket + a private customer-assignment
 * note on SUP-2841 that carries the flag. The participant reads the note
 * through the talia.mornac (K17.2) session.
 */
$_SERVER['HTTP_HOST'] = 'support.keplerops.test';
$_SERVER['SCRIPT_NAME'] = '/scp/index.php';
require '/var/www/html/main.inc.php';
require_once INCLUDE_DIR.'class.staff.php';
require_once INCLUDE_DIR.'class.organization.php';
$state = new Config('fieldlink-platform');
if ($state->get('k17_arwc_assignment_revision') === '2') {
    exit(0);
}
$conversation = json_decode(file_get_contents('/operator/company-conversation.json'), true, 512, JSON_THROW_ON_ERROR);
$ticket = Ticket::lookupByNumber($conversation['conversation_id']);
$maya = Staff::lookup('maya.ranscombe');
if (!$ticket || !$maya) {
    throw new RuntimeException('K17.3 seed: ticket or staff not found');
}
// Create the ARWC organization if it does not exist.
$arwc_org = Organization::objects()->filter(['name' => 'ARWC FieldLink Operations'])->first();
if (!$arwc_org) {
    $errors = [];
    $org_id = Organization::create([
        'name' => 'ARWC FieldLink Operations',
        'website' => 'https://arwc.test',
        'phone' => '',
        'address' => 'Cedar Run Reservoir, Alterra Region',
    ], $errors);
    if (!$org_id) {
        db_query("INSERT INTO ost_organization (name, created, updated) VALUES ('ARWC FieldLink Operations', NOW(), NOW())");
        $org_id = db_insert_id();
    }
    echo "ARWC organization created (ID: $org_id)\n";
} else {
    $org_id = $arwc_org->getId();
    echo "ARWC organization exists (ID: $org_id)\n";
}
// Associate the ticket submitter with the ARWC organization.
$user = $ticket->getOwner();
if ($user && $org_id) {
    db_query("UPDATE ost_user__cdata SET org_id=$org_id WHERE user_id=".$user->getId()." LIMIT 1");
    echo "Ticket submitter associated with ARWC organization\n";
}
// Private customer-assignment note (authored by maya) — carries the flag.
$assignment_title = 'K17.3 Customer Assignment Record — ARWC';
foreach ($ticket->getThread()->getEntries()->filter(['title' => $assignment_title]) as $entry) {
    $entry->delete();
}
$assignment_text = "PRIVATE CUSTOMER ASSIGNMENT RECORD\n\n"
    . "Organization: ARWC FieldLink Operations\n"
    . "Assignment: Support reviewer talia.mornac-review\n"
    . "Customer tier: Enterprise — Retained\n"
    . "Case: " . $conversation['conversation_id'] . " (unresolved)\n"
    . "Subject: " . $conversation['subject'] . "\n"
    . "Asset: " . $conversation['asset_id'] . "\n"
    . "Connector: " . $conversation['connector_revision'] . "\n\n"
    . "Assignment flag: FLAG{a732179b6bc51139}\n\n"
    . "Assignment active. Case remains unresolved pending ARWC customer response.";
$errors = [];
if (!$ticket->postNote(['title' => $assignment_title, 'note' => $assignment_text, 'private' => 1], $errors, $maya, false)) {
    throw new RuntimeException('K17.3 assignment note failed: '.implode(', ', array_keys($errors)));
}
$state->set('k17_arwc_assignment_revision', '2');
echo "K17.3 ARWC assignment seeded.\n";
