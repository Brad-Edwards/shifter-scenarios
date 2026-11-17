FROM gotenberg/gotenberg:9.4.1@sha256:7d790c081a944f4d30cacb59a2cdccbe71569532af691b93c36551f6a877b4fc
USER root
RUN apt-get update \
    && apt-get install --no-install-recommends -y iproute2 python3 python3-cryptography \
    && rm -rf /var/lib/apt/lists/*
COPY build/keplerops/runtime/http_support.py /opt/fieldkest-preview/http_support.py
COPY build/keplerops/runtime/credentials.py /opt/fieldkest-preview/credentials.py
COPY build/keplerops/runtime/preview.py /opt/fieldkest-preview/preview.py
COPY build/keplerops/runtime/preview-client.json /opt/fieldkest-preview/client_documents.json
COPY build/keplerops/native-preview/entrypoint.sh /usr/local/bin/fieldlink-preview-entrypoint
COPY assets/keplerops/registry/k-preview-state.tar /tmp/k-preview-state.tar
RUN useradd --system --home-dir /var/lib/fieldkest-preview --shell /usr/sbin/nologin fieldkest-preview \
    && mkdir -p /var/lib/fieldkest-preview \
    && tar -xf /tmp/k-preview-state.tar -C /var/lib/fieldkest-preview \
    && mkdir -p /var/lib/fieldkest-preview/audit /var/lib/fieldkest-preview/results \
    && chown -R fieldkest-preview:fieldkest-preview /var/lib/fieldkest-preview \
    && rm /tmp/k-preview-state.tar \
    && ln -s /opt/fieldkest-preview /opt/fieldkest
RUN chmod 0555 /usr/local/bin/fieldlink-preview-entrypoint
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldlink-preview-entrypoint"]
CMD ["gotenberg"]
