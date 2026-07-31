<?php

$config['db_dsnw'] = 'sqlite:////var/roundcube/db/roundcube.sqlite?mode=0640';
$config['imap_host'] = 'ssl://mail-server-01.keplerops.lab:993';
$config['smtp_host'] = 'tls://mail-server-01.keplerops.lab:587';
$config['smtp_user'] = '%u';
$config['smtp_pass'] = '%p';
$config['username_domain'] = 'keplerops.test';
$config['mail_domain'] = 'keplerops.test';
$config['product_name'] = 'KeplerOps Mail';
$config['des_key'] = 'KeplerOps-Roundcube-2026-32-byte!'; // NOSONAR - synthetic range key
$config['temp_dir'] = '/tmp/roundcube-temp';
$config['enable_installer'] = false;
$config['plugins'] = ['archive', 'zipdownload'];
$config['imap_conn_options'] = [
    'ssl' => [
        'verify_peer' => true,
        'verify_peer_name' => true,
        'allow_self_signed' => false,
        'cafile' => '/etc/keplerops/pki/ca.crt',
        'peer_name' => 'mail-server-01.keplerops.lab',
    ],
];
$config['smtp_conn_options'] = $config['imap_conn_options'];
