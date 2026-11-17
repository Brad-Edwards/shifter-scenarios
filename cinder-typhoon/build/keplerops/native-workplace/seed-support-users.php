<?php
$_SERVER['HTTP_HOST'] = 'support.keplerops.test';
$_SERVER['SCRIPT_NAME'] = '/scp/index.php';
require '/var/www/html/main.inc.php';
require_once INCLUDE_DIR.'class.staff.php';
$state = new Config('fieldlink-platform');
if ($state->get('staff_import_revision') === '1') {
    exit(0);
}
$input = json_decode(file_get_contents('/run/fieldlink/support-accounts.json'), true, 512, JSON_THROW_ON_ERROR);
$department = Dept::objects()->filter(['name' => 'Support'])->first();
if (!$department) {
    throw new RuntimeException('Native support department was not found');
}
$thisstaff = Staff::lookup('platform-admin');
foreach ($input['users'] as $value) {
    $role = Role::lookup(['name' => $value['role']]);
    if (!$role) {
        throw new RuntimeException('Native staff role was not found');
    }
    $staff = Staff::lookup($value['username']);
    if (!$staff) {
        $staff = Staff::create([
            'username' => $value['username'], 'firstname' => $value['firstname'],
            'lastname' => $value['lastname'], 'email' => $value['username'].'@keplerops.test',
            'dept_id' => $department->getId(), 'role_id' => $role->getId(),
            'isadmin' => 0, 'isactive' => 1, 'change_passwd' => 0,
        ]);
        if (!$staff->save()) {
            throw new RuntimeException('Native support user creation failed');
        }
    }
    if (!$staff->hasPassword()) {
        $staff->setPassword($value['password']);
        if (!$staff->save()) {
            throw new RuntimeException('Native support password setup failed');
        }
    }
}
$state->set('staff_import_revision', '1');
echo "Native support staff imported.\n";
