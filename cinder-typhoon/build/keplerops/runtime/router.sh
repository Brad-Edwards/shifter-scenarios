#!/bin/sh
set -eu

iptables -P FORWARD DROP
iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A FORWARD -s 10.77.50.20 -d 10.77.51.20 -p tcp --dport 443 -j ACCEPT
iptables -A FORWARD -s 10.77.50.20 -d 10.77.51.30 -p tcp --dport 443 -j ACCEPT
iptables -A FORWARD -s 10.77.50.20 -d 10.77.51.40 -p tcp --dport 443 -j ACCEPT
iptables -A FORWARD -s 10.77.50.20 -d 10.77.51.60 -p tcp --dport 443 -j ACCEPT
iptables -A FORWARD -s 10.77.53.0/24 -d 10.77.51.20 -p tcp --dport 443 -j ACCEPT
iptables -A FORWARD -s 10.77.53.0/24 -d 10.77.51.30 -p tcp --dport 443 -j ACCEPT
iptables -A FORWARD -s 10.77.53.0/24 -d 10.77.50.30 -p tcp --dport 443 -j ACCEPT
iptables -A FORWARD -s 10.77.53.0/24 -d 10.77.50.50 -p tcp --dport 443 -j ACCEPT
iptables -A FORWARD -s 10.77.53.0/24 -d 10.77.52.20 -p tcp --dport 443 -j ACCEPT
iptables -A FORWARD -s 10.77.53.0/24 -d 10.77.52.30 -p tcp --dport 443 -j ACCEPT
exec tail -f /dev/null
