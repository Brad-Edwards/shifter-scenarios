FROM alpine:3.19@sha256:6baf43584bcb78f2e5847d1de515f23499913ac9f12bdf834811a3145eb11ca1

RUN apk add --no-cache nmap nmap-scripts nmap-ncat tcpdump python3 py3-pip openssh bash && \
    pip3 install --break-system-packages pymodbus==3.12.1 && \
    ssh-keygen -A && mkdir /run/sshd

# Content files live in A9-splice-landing/ per convention; build context
# is the parent mechag/ dir.
COPY A9-splice-landing/README.txt /root/README.txt
COPY A9-splice-landing/scan_results.txt /root/scan_results.txt
COPY A9-splice-landing/modbus_client.py /usr/local/bin/modbus_client.py
RUN chmod +x /usr/local/bin/modbus_client.py

# Set root password for SSH access
RUN echo "root:splice2025" | chpasswd

# Allow root SSH login
# The splice-relay key (A9_AUTHORIZED_KEY) is the only path in;
# disable password auth and allow root login by key only.
RUN sed -i 's/#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config && \
    sed -i 's/#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config

COPY a9/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
