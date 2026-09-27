FROM ubuntu:24.04 AS native
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install --no-install-recommends -y binutils g++ libsodium-dev \
    && rm -rf /var/lib/apt/lists/*
COPY build/arwc/runtime/estimator23.cpp /tmp/estimator23.cpp
COPY build/arwc/runtime/signer24.c /tmp/signer24.c
RUN g++ -std=c++20 -O2 -fno-omit-frame-pointer -static-libstdc++ -static-libgcc -Wl,--build-id=none \
      -o /tmp/estimator23 /tmp/estimator23.cpp \
    && strip --strip-all /tmp/estimator23 \
    && /tmp/estimator23 --ordinary | grep -F 'Cairn=12.40' \
    && gcc -O2 -fPIE -pie -Wl,-z,relro,-z,now,--build-id=none -o /tmp/dsign-crr-r3 /tmp/signer24.c -lsodium \
    && strip --strip-all /tmp/dsign-crr-r3 \
    && /tmp/dsign-crr-r3 --contract | grep -F 'CRR25519-S'

FROM ubuntu:24.04
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libsodium23 python3 python3-cryptography util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system arwc-diagnostics \
    && useradd --system --gid arwc-diagnostics --home-dir /var/lib/arwc-diagnostics --shell /usr/sbin/nologin arwc-diagnostics \
    && install -d -o arwc-diagnostics -g arwc-diagnostics -m 0750 /opt/diagnostic-services/artifacts
COPY --chown=arwc-diagnostics:arwc-diagnostics --chmod=0640 build/arwc/runtime/diagnostic_services.py /opt/diagnostic-services/diagnostic_services.py
COPY --from=native --chown=arwc-diagnostics:arwc-diagnostics --chmod=0750 /tmp/estimator23 /opt/diagnostic-services/artifacts/estimator23
COPY --from=native --chown=arwc-diagnostics:arwc-diagnostics --chmod=0750 /tmp/dsign-crr-r3 /opt/diagnostic-services/artifacts/dsign-crr-r3
COPY --chmod=0750 build/arwc/runtime/diagnostics-entrypoint.sh /usr/local/sbin/arwc-diagnostics-entrypoint
EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-diagnostics-entrypoint"]
