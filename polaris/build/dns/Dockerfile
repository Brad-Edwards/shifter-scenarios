FROM alpine:3.19@sha256:6baf43584bcb78f2e5847d1de515f23499913ac9f12bdf834811a3145eb11ca1

RUN apk add --no-cache bind

COPY named.conf /etc/bind/named.conf
COPY db.boreas-systems.ctf /etc/bind/db.boreas-systems.ctf
COPY db.boreas.local /etc/bind/db.boreas.local
COPY entrypoint.sh /usr/local/bin/dns-entrypoint.sh

RUN mkdir -p /var/run/named && \
    chown named:named /var/run/named && \
    chmod +x /usr/local/bin/dns-entrypoint.sh

EXPOSE 53/udp 53/tcp
ENTRYPOINT ["/usr/local/bin/dns-entrypoint.sh"]
