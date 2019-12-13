#!/bin/bash

if [[ $(</etc/hostname) != "nuclet" ]]; then
  echo "You should run this from the host, not inside the container."
  exit
fi

set -x

# systemd-nspawn
cp /etc/systemd/nspawn/etrial.nspawn /home/scott/git/etrial/config

# systemd-networkd
cp /var/lib/machines/etrial/etc/systemd/network/mv-eno1.network /home/scott/git/etrial/config

# openssh
cp /var/lib/machines/etrial/etc/ssh/sshd_config /home/scott/git/etrial/config

# nginx
cp /var/lib/machines/etrial/etc/nginx/nginx.conf /home/scott/git/etrial/config

# gunicorn
cp /var/lib/machines/etrial/etc/systemd/system/gunicorn.service /home/scott/git/etrial/config

chown -R scott:scott /home/scott/git/etrial/config
