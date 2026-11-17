#!/bin/sh
set -eu

install -d -m 0755 -o named -g named /run/named /var/cache/bind
named-checkconf /etc/bind/named.conf
named-checkzone keplerops.test /etc/bind/db.keplerops.test
exec named -g -u named -c /etc/bind/named.conf
