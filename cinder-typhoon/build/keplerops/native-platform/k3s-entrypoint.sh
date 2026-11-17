#!/bin/sh
set -eu
# The participant networks have no Internet route. K3s still requires a default
# route for its own interface selection and ClusterIP routing.
if ! ip route show default | grep -q .; then
  ip link add dummy0 type dummy
  ip link set dummy0 up
  ip addr add 203.0.113.254/31 dev dummy0
  ip route add default via 203.0.113.255 dev dummy0 metric 1000
fi
exec /bin/k3s "$@"
