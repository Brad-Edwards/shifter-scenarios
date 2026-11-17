<?php
// Run the upstream installer with private runtime inputs, outside the web UI.
$input = json_decode(file_get_contents('/run/fieldlink/support-bootstrap.json'), true, 512, JSON_THROW_ON_ERROR);
$configuration = '/var/www/html/include/ost-config.php';
$db = new mysqli($input['dbhost'], $input['dbuser'], $input['dbpass'], $input['dbname']);
$tables = $db->query("SHOW TABLES LIKE 'ost_config'");
if ($tables->num_rows > 0) {
    if (!str_contains(file_get_contents($configuration), "define('OSTINSTALLED',TRUE)")) {
        throw new RuntimeException('Existing support database requires its retained configuration');
    }
    echo "Native support installation retained.\n";
    exit(0);
}
$db->close();
copy('/var/www/html/include/ost-sampleconfig.php', $configuration);
$_SERVER['HTTP_HOST'] = 'support.keplerops.test';
$_SERVER['PHP_SELF'] = '/setup/install.php';
$_SERVER['HTTPS'] = 'on';
chdir('/var/www/html/setup');
require 'setup.inc.php';
require_once INC_DIR.'class.installer.php';
$installer = new Installer($configuration);
if (!$installer->install($input)) {
    throw new RuntimeException('Native osTicket installation failed');
}
file_put_contents($configuration, str_replace("define('TRUSTED_PROXIES', '');",
    "define('TRUSTED_PROXIES', '10.77.56.11');", file_get_contents($configuration)));
chgrp($configuration, 33);
chmod($configuration, 0640);
echo "Native support application installed.\n";
