#!/bin/bash

if [[ $(</proc/sys/kernel/hostname) != "etrial" ]]; then
  echo "You should run this from inside the container."
  exit
fi

key=$(pwgen -1 4 4)
mkdir -p .secure secure
gocryptfs -passfile <(echo $key) -init .secure
gocryptfs -passfile <(echo $key) .secure secure

