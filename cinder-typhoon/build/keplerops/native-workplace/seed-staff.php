<?php
// One-time administration import; ordinary records remain owned by Kanboard.
chdir('/var/www/app');
if (file_exists('data/.fieldlink-seeded')) {
    exit(0);
}
require 'app/common.php';
$container['dispatcher']->dispatch(new Symfony\Contracts\EventDispatcher\Event(), 'app.bootstrap');
$input = json_decode(file_get_contents('/run/fieldlink/kanboard-bootstrap.json'), true, 512, JSON_THROW_ON_ERROR);
$admin = $container['userModel']->getByUsername('admin');
if (!$container['userModel']->update(['id' => $admin['id'], 'password' => $input['admin_password']])) {
    throw new RuntimeException('Staff administrator initialization failed');
}
$users = [];
foreach ($input['users'] as $value) {
    $existing = $container['userModel']->getByUsername($value['username']);
    if (!$existing) {
        $value['email'] = $value['username'].'@keplerops.test';
        $id = $container['userModel']->create($value);
        if (!$id) {
            throw new RuntimeException('Staff user import failed');
        }
        $existing = $container['userModel']->getById($id);
    }
    $users[$value['username']] = $existing['id'];
}
$project = $container['projectModel']->getByIdentifier('FIELDLINK');
if (!$project) {
    $id = $container['projectModel']->create([
        'name' => 'FieldLink release operations', 'identifier' => 'FIELDLINK',
        'is_private' => 0, 'owner_id' => $users['talia.mornac'],
        'description' => 'Release reviews, customer handovers and retained engineering records.',
    ]);
    if (!$id) {
        throw new RuntimeException('Staff project import failed');
    }
    $project = $container['projectModel']->getById($id);
}
foreach (['rowan.ito' => 'project-member', 'maya.ranscombe' => 'project-viewer', 'talia.mornac' => 'project-manager'] as $name => $role) {
    if (!$container['db']->table('project_has_users')->eq('project_id', $project['id'])->eq('user_id', $users[$name])->exists()) {
        if (!$container['projectUserRoleModel']->addUser($project['id'], $users[$name], $role)) {
            throw new RuntimeException('Staff project role import failed');
        }
    }
}
$reference = 'REL-FLK-7.4.2-09';
$task = $container['db']->table('tasks')->eq('project_id', $project['id'])->eq('reference', $reference)->findOne();
if (!$task) {
    $id = $container['taskCreationModel']->create([
        'project_id' => $project['id'], 'title' => 'FieldLink 7.4.2 release review',
        'reference' => $reference, 'creator_id' => $users['rowan.ito'], 'owner_id' => $users['rowan.ito'],
        'description' => 'The current review export contains unresolved provider-report comments. Retain the producing job and report digest with the customer handover.',
    ]);
    if (!$id) {
        throw new RuntimeException('Release review import failed');
    }
    $task = $container['taskFinderModel']->getById($id);
}
$export = file_get_contents('/opt/fieldlink/review-export.md');
if (!$container['db']->table('task_has_files')->eq('task_id', $task['id'])->eq('name', 'fieldlink-7.4.2-review.md')->exists()) {
    if (!$container['taskFileModel']->uploadContent($task['id'], 'fieldlink-7.4.2-review.md', $export, false, $users['rowan.ito'])) {
        throw new RuntimeException('Review attachment import failed');
    }
}
preg_match_all('/^- `([^`]+)`: (.+?)(?=\n- `|\z)/ms', $export, $comments, PREG_SET_ORDER);
foreach ($comments as $comment) {
    $body = $comment[1].': '.preg_replace('/\s+/', ' ', trim($comment[2]));
    if (!$container['db']->table('comments')->eq('task_id', $task['id'])->eq('comment', $body)->exists()) {
        if (!$container['commentModel']->create(['task_id' => $task['id'], 'user_id' => $users['rowan.ito'], 'comment' => $body])) {
            throw new RuntimeException('Review comment import failed');
        }
    }
}
$container['configModel']->save(['application_url' => 'https://staff.keplerops.test/']);
file_put_contents('data/.fieldlink-seeded', "FieldLink workplace import complete\n");
echo "Native staff records imported.\n";
