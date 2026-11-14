FROM alpine:3.19@sha256:6baf43584bcb78f2e5847d1de515f23499913ac9f12bdf834811a3145eb11ca1
RUN apk add --no-cache bind=9.18.44-r0 bind-tools=9.18.44-r0
COPY named.conf /etc/bind/named.conf
COPY db.arwc.test /etc/bind/db.arwc.test
CMD ["named", "-g", "-u", "named", "-c", "/etc/bind/named.conf"]
