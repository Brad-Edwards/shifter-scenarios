FROM python:3.12.11-slim-bookworm AS narrative
COPY assets/narrative/generated/packages/arwc-documents.json /tmp/arwc-documents.json
COPY build/arwc/runtime/extract_document.py /usr/local/bin/extract-document
RUN python3 /usr/local/bin/extract-document /tmp/arwc-documents.json me-project-handover-01 /tmp/me-project-handover-01.md

FROM debian:bookworm-slim AS native
RUN apt-get update \
    && apt-get install --no-install-recommends -y binutils gcc libc6-dev python3 \
    && rm -rf /var/lib/apt/lists/*
COPY build/arwc/runtime/mixed-diagnostic.S /tmp/mixed-diagnostic.S
COPY build/arwc/runtime/dpg1.py build/arwc/runtime/generate_dpg1.py build/arwc/runtime/rot128_verifier.c /tmp/w27-src/
RUN gcc -nostdlib -static -no-pie -Wl,--build-id=none \
      -o /tmp/diag-crr-mixed-19 /tmp/mixed-diagnostic.S \
    && strip --strip-all /tmp/diag-crr-mixed-19 \
    && cd /tmp/w27-src \
    && python3 generate_dpg1.py /tmp/w27 \
    && gcc -O2 -fPIE -pie -Wl,-z,relro,-z,now,--build-id=none \
      -I/tmp/w27 -o /tmp/w27/rot128-verifier rot128_verifier.c \
    && strip --strip-all /tmp/w27/rot128-verifier \
    && /tmp/w27/rot128-verifier /tmp/w27/base.dpg | grep -F '"decision":"accepted"'

FROM nimlang/nim:2.0.8 AS viewer
COPY build/arwc/runtime/sealed_viewer.nim /tmp/sealed_viewer.nim
RUN nim c -d:release --opt:size --passL:-Wl,--build-id=none \
      -o:/tmp/sealed-viewer /tmp/sealed_viewer.nim \
    && strip --strip-all /tmp/sealed-viewer

FROM python:3.12.11-slim-bookworm AS sealed
RUN pip install --no-cache-dir cryptography==42.0.8
COPY build/arwc/runtime/generate_process_artifacts.py /tmp/generate-process-artifacts
RUN python3 /tmp/generate-process-artifacts sealed /tmp/sealed

FROM mcr.microsoft.com/dotnet/sdk:8.0-bookworm-slim AS review
RUN apt-get update \
    && apt-get install --no-install-recommends -y python3 \
    && rm -rf /var/lib/apt/lists/*
COPY build/arwc/runtime/ReviewHelper.csproj build/arwc/runtime/ReviewHelper.cs /tmp/review/
COPY build/arwc/runtime/patch_review_helper.py /tmp/patch-review-helper
RUN dotnet publish /tmp/review/ReviewHelper.csproj -c Release -r linux-x64 \
      --self-contained false -p:PublishReadyToRun=true -o /tmp/review-out \
    && python3 /tmp/patch-review-helper /tmp/review-out/ReviewHelper.dll \
    && test "$(dotnet /tmp/review-out/ReviewHelper.dll)" = 'REVIEWHELP-R4:elias.vorn-review:CMP-CRR-R21-R7' \
    && test "$(COMPlus_ReadyToRun=0 dotnet /tmp/review-out/ReviewHelper.dll)" = 'REVIEWHELP-R4:mara.stone-review:CMP-CRR-R21-R7'

FROM python:3.12.11-slim-bookworm
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2320 arwc-process-evidence \
    && groupadd --system arwc-engineering \
    && useradd --system --gid arwc-engineering --groups arwc-process-evidence --home-dir /var/lib/arwc-engineering --shell /usr/sbin/nologin arwc-engineering \
    && install -d -o arwc-engineering -g arwc-engineering -m 0750 \
      /opt/process-service/assets /opt/process-service/artifacts
RUN pip install --no-cache-dir cryptography==42.0.8
COPY --chown=arwc-engineering:arwc-engineering --chmod=0640 build/arwc/runtime/process_services.py /opt/process-service/process_services.py
COPY --chown=arwc-engineering:arwc-engineering --chmod=0640 build/arwc/runtime/dpg1.py /opt/process-service/dpg1.py
COPY --from=narrative --chown=arwc-engineering:arwc-engineering --chmod=0640 /tmp/me-project-handover-01.md /opt/process-service/assets/me-project-handover-01.md
COPY --from=native --chown=arwc-engineering:arwc-engineering --chmod=0750 /tmp/diag-crr-mixed-19 /opt/process-service/artifacts/diag-crr-mixed-19
COPY --from=viewer --chown=arwc-engineering:arwc-engineering --chmod=0750 /tmp/sealed-viewer /opt/process-service/artifacts/sealed-viewer
COPY --from=sealed --chown=arwc-engineering:arwc-engineering --chmod=0640 /tmp/sealed/ /opt/process-service/artifacts/
COPY --from=review --chown=arwc-engineering:arwc-engineering --chmod=0640 /tmp/review-out/ReviewHelper.dll /opt/process-service/artifacts/ReviewHelper.dll
COPY --from=native --chown=arwc-engineering:arwc-engineering /tmp/w27/ /opt/process-service/artifacts/w27/
COPY --chmod=0750 build/arwc/runtime/process-service-entrypoint.sh /usr/local/sbin/arwc-process-entrypoint
EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-process-entrypoint"]
