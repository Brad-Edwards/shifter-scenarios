FROM alpine:3.19@sha256:6baf43584bcb78f2e5847d1de515f23499913ac9f12bdf834811a3145eb11ca1
RUN apk add --no-cache krb5=1.21.3-r0 krb5-server=1.21.3-r0
COPY krb5.conf /etc/krb5.conf
COPY kdc.conf /etc/krb5kdc/kdc.conf
COPY kerberos-entrypoint.sh /usr/local/bin/arwc-kdc
RUN chmod 0755 /usr/local/bin/arwc-kdc
ENTRYPOINT ["/usr/local/bin/arwc-kdc"]
