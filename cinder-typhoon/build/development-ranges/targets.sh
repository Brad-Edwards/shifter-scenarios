#!/usr/bin/env bash

# These values are consumed by scripts that source this target map.
# shellcheck disable=SC2034

cinder_load_development_target() {
  case ${1-} in
    fieldlink)
      CINDER_DEV_TARGET=fieldlink
      CINDER_DEV_INSTANCE=cinder-fieldlink-dev
      CINDER_DEV_PRIVATE_IP=10.77.49.9
      CINDER_DEV_SOURCE_INSTANCE=cinder-keplerops-golden
      CINDER_DEV_MACHINE_IMAGE=cinder-fieldlink-golden-preserved-20261114
      CINDER_DEV_NETWORK=cinder-keplerops-golden
      CINDER_DEV_SUBNET=cinder-keplerops-carrier
      CINDER_DEV_TAG=cinder-keplerops-carrier
      CINDER_DEV_REMOTE_ROOT=/opt/cinder-typhoon
      CINDER_DEV_READY_MARKER=/var/lib/cinder-fieldlink-development-ready
      ;;
    arwc)
      CINDER_DEV_TARGET=arwc
      CINDER_DEV_INSTANCE=cinder-arwc-dev
      CINDER_DEV_PRIVATE_IP=10.77.59.11
      CINDER_DEV_SOURCE_INSTANCE=cinder-arwc-ot-compat-363
      CINDER_DEV_MACHINE_IMAGE=cinder-arwc-ot-backup-20261113-qualified
      CINDER_DEV_NETWORK=cinder-arwc-golden
      CINDER_DEV_SUBNET=cinder-arwc-carrier
      CINDER_DEV_TAG=cinder-arwc-carrier
      CINDER_DEV_REMOTE_ROOT=/opt/arwc-ot-compat/it/cinder-typhoon
      CINDER_DEV_READY_MARKER=/var/lib/cinder-arwc-development-ready
      ;;
    *)
      echo 'TARGET must be fieldlink or arwc' >&2
      return 2
      ;;
  esac
}

cinder_validate_development_target() {
  [[ ${CINDER_DEV_INSTANCE-} == cinder-*-dev ]] || return 1
  [[ $CINDER_DEV_INSTANCE != *golden* ]] || return 1
  [[ $CINDER_DEV_INSTANCE != "$CINDER_DEV_SOURCE_INSTANCE" ]] || return 1
  [[ ${CINDER_DEV_REMOTE_ROOT-} == /opt/* ]] || return 1
  case $CINDER_DEV_TARGET in
    fieldlink) [[ $CINDER_DEV_PRIVATE_IP == 10.77.49.9 ]] || return 1 ;;
    arwc) [[ $CINDER_DEV_PRIVATE_IP == 10.77.59.11 ]] || return 1 ;;
    *) return 1 ;;
  esac
}
