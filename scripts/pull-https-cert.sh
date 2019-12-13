#!/bin/bash

if [[ $(</etc/hostname) != "nuclet" ]]; then
  echo "You should run this from the host, not inside the container."
  exit
fi

set -x

cp /var/lib/machines/etrial/home/etrial/https/*.pfx /home/scott/git/etrial
chown scott:scott /home/scott/git/etrial/*.pfx
