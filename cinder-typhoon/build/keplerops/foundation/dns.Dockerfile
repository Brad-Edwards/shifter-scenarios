FROM alpine:3.19@sha256:6baf43584bcb78f2e5847d1de515f23499913ac9f12bdf834811a3145eb11ca1

RUN apk add --no-cache bind=9.18.44-r0 bind-tools=9.18.44-r0

COPY build/keplerops/foundation/named.conf /etc/bind/named.conf
COPY build/keplerops/foundation/db.keplerops.test /etc/bind/db.keplerops.test
COPY build/keplerops/foundation/dns-entrypoint.sh /usr/local/bin/fieldlink-dns-entrypoint
RUN chmod 0755 /usr/local/bin/fieldlink-dns-entrypoint

EXPOSE 53/tcp 53/udp
ENTRYPOINT ["/usr/local/bin/fieldlink-dns-entrypoint"]
