#!/bin/bash

set -x

groupadd sftp

for account in judge jury witness; do
    useradd $account -s /bin/false -d /secure/$account
    mkdir -p /secure/$account/.ssh
    chown -R $account:etrial /secure/$account

    >> /etc/ssh/sshd_config echo '
    Match User jury
    ForceCommand internal-sftp
    ChrootDirectory /home/jury
    PermitTunnel no
    AllowAgentForwarding no
    AllowTcpForwarding no
    X11Forwarding no'
done

chmod 770 -R /secure

for account in judge jury witness; do
  chmod 700 /secure/$account/.ssh
  chmod 600 /secure/$account/.ssh/authorized_keys
done
