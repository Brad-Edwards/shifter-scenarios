FROM alpine:3.22
RUN apk add --no-cache iptables
COPY build/keplerops/runtime/router.sh /router.sh
RUN chmod 0755 /router.sh
ENTRYPOINT ["/router.sh"]

