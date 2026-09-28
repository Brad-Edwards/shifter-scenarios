FROM alpine:3.22

RUN apk add --no-cache socat \
    && addgroup -S fieldlink-edge \
    && adduser -S -D -H -G fieldlink-edge fieldlink-edge

USER fieldlink-edge:fieldlink-edge
EXPOSE 443
ENTRYPOINT ["socat", "TCP4-LISTEN:443,reuseaddr,fork", "TCP4:10.77.60.20:443"]
