<?php

declare(strict_types=1);

use Mautic\UserBundle\Entity\Role;

defined('IN_MAUTIC_CONSOLE') || define('IN_MAUTIC_CONSOLE', 1);
defined('MAUTIC_ROOT_DIR') || define('MAUTIC_ROOT_DIR', '/var/www/html/docroot');

require '/var/www/html/docroot/app/config/bootstrap.php';

$kernel = new AppKernel($_SERVER['APP_ENV'], (bool) $_SERVER['APP_DEBUG']);
$kernel->boot();

$model = $kernel->getContainer()->get('mautic.user.model.role');
$role = $model->getRepository()->findOneBy(['name' => 'Communications']);
if (!$role instanceof Role) {
    $role = new Role();
}

$role->setName('Communications');
$role->setDescription('Publishes KeplerOps product communications without administrative access.');
$role->setIsAdmin(false);
$model->setRolePermissions($role, [
    'asset:assets' => ['viewown', 'viewother', 'editown', 'create', 'deleteown', 'publishown'],
    'email:emails' => ['viewown', 'viewother', 'editown', 'create', 'deleteown', 'publishown'],
    'page:pages' => ['viewown', 'viewother', 'editown', 'create', 'deleteown', 'publishown'],
    'lead:leads' => ['viewown', 'viewother'],
    'user:profile' => ['editname'],
]);
$model->saveEntity($role);

if ($role->isAdmin()) {
    throw new RuntimeException('Communications role must remain non-admin.');
}

printf("ROLE_ID=%d\n", $role->getId());

$kernel->shutdown();
