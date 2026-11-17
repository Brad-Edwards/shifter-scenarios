FROM gotenberg/gotenberg:9.4.1@sha256:7d790c081a944f4d30cacb59a2cdccbe71569532af691b93c36551f6a877b4fc
USER root
RUN apt-get update \
    && apt-get install --no-install-recommends -y iproute2 \
    && rm -rf /var/lib/apt/lists/*
COPY build/keplerops/native-preview/entrypoint.sh /usr/local/bin/fieldlink-preview-entrypoint
RUN chmod 0555 /usr/local/bin/fieldlink-preview-entrypoint
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldlink-preview-entrypoint"]
CMD ["gotenberg"]
