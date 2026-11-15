<?php
$_SERVER['HTTP_HOST'] = 'support.keplerops.test';
$_SERVER['SCRIPT_NAME'] = '/scp/index.php';
require '/var/www/html/main.inc.php';
require_once INCLUDE_DIR.'class.staff.php';
$state = new Config('fieldlink-platform');
if ($state->get('company_case_import_revision') === '1') {
    exit(0);
}
$conversation = json_decode(file_get_contents('/operator/company-conversation.json'), true, 512, JSON_THROW_ON_ERROR);
$ticket = Ticket::lookupByNumber($conversation['conversation_id']);
$thisstaff = Staff::lookup('maya.ranscombe');
if (!$thisstaff) {
    throw new RuntimeException('Native company case owner was not found');
}
if (!$ticket) {
    $errors = [];
    $ticket = Ticket::create([
        'name' => 'ARWC FieldLink Operations', 'email' => 'fieldlink-operations@arwc.test',
        'subject' => $conversation['subject'],
        'message' => 'Retained support conversation for '.$conversation['customer'].'. Asset '.$conversation['asset_id'].', connector '.$conversation['connector_revision'].'.',
        'topicId' => 1, 'deptId' => $thisstaff->getDeptId(),
        'staffId' => $thisstaff->getId(), 'source' => 'Email',
    ], $errors, 'Email', false, false);
    if (!$ticket) {
        throw new RuntimeException('Native company case import failed: '.implode(', ', array_keys($errors)));
    }
    $ticket->number = $conversation['conversation_id'];
    if (!$ticket->save()) {
        throw new RuntimeException('Native company case reference import failed');
    }
}
foreach ($conversation['messages'] as $message) {
    $title = 'Retained correspondence '.$message['at'];
    if ($ticket->getThread()->getEntries()->filter(['title' => $title])->count()) {
        continue;
    }
    $author = Staff::lookup(explode('@', $message['from'])[0]);
    $errors = [];
    if (!$ticket->postNote(['title' => $title, 'note' => $message['text']], $errors, $author, false)) {
        throw new RuntimeException('Native company correspondence import failed');
    }
}
$state->set('company_case_import_revision', '1');
echo "Native company support case imported.\n";
