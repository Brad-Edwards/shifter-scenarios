<?php
$_SERVER['HTTP_HOST'] = 'support.keplerops.test';
$_SERVER['SCRIPT_NAME'] = '/scp/index.php';
require '/var/www/html/main.inc.php';
require_once INCLUDE_DIR.'class.staff.php';
$state = new Config('fieldlink-platform');
if ($state->get('company_case_import_revision') === '2') {
    exit(0);
}
$conversation = json_decode(file_get_contents('/operator/company-conversation.json'), true, 512, JSON_THROW_ON_ERROR);
$ticket = Ticket::lookupByNumber($conversation['conversation_id']);
$owner = Staff::lookup('maya.ranscombe');
$thisstaff = Staff::lookup('platform-admin');
if (!$owner || !$thisstaff) {
    throw new RuntimeException('Native company case owner was not found');
}
if (!$ticket) {
    $customer = User::fromVars([
        'name' => 'ARWC FieldLink Operations', 'email' => 'fieldlink-operations@arwc.test',
    ]);
    if (!$customer) {
        throw new RuntimeException('Native company contact import failed');
    }
    $errors = [];
    $ticket = Ticket::create([
        'uid' => $customer->getId(),
        'name' => 'ARWC FieldLink Operations', 'email' => 'fieldlink-operations@arwc.test',
        'subject' => $conversation['subject'],
        'message' => 'Retained support conversation for '.$conversation['customer'].'. Asset '.$conversation['asset_id'].', connector '.$conversation['connector_revision'].'.',
        'topicId' => 1, 'deptId' => $owner->getDeptId(),
        'staffId' => $owner->getId(), 'source' => 'Email',
    ], $errors, 'Staff', false, false);
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
$ordinary = json_decode(file_get_contents('/operator/support-cases.json'), true, 512, JSON_THROW_ON_ERROR);
foreach ($ordinary['tickets'] as $record) {
    $existing = Ticket::lookupByNumber($record['number']);
    if (!$existing) {
        $customer = User::fromVars(['name' => $record['customer'], 'email' => $record['email']]);
        if (!$customer) {
            throw new RuntimeException('Native ordinary support contact import failed');
        }
        $errors = [];
        $existing = Ticket::create([
            'uid' => $customer->getId(), 'name' => $record['customer'], 'email' => $record['email'],
            'subject' => $record['subject'], 'message' => $record['opening'],
            'topicId' => 1, 'deptId' => $owner->getDeptId(), 'staffId' => $owner->getId(), 'source' => 'Email',
        ], $errors, 'Staff', false, false);
        if (!$existing) {
            throw new RuntimeException('Native ordinary support case import failed: '.implode(', ', array_keys($errors)));
        }
        $existing->number = $record['number'];
        if (!$existing->save()) {
            throw new RuntimeException('Native ordinary support reference import failed');
        }
    }
    foreach ($record['notes'] as $index => $note) {
        $title = 'Service correspondence '.($index + 1);
        if (!$existing->getThread()->getEntries()->filter(['title' => $title])->count()) {
            $errors = [];
            if (!$existing->postNote(['title' => $title, 'note' => $note], $errors, $owner, false)) {
                throw new RuntimeException('Native ordinary support correspondence import failed');
            }
        }
    }
}
$state->set('company_case_import_revision', '2');
echo "Native company support cases imported.\n";
