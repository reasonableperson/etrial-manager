#!/bin/bash

if [[ $(</proc/sys/kernel/hostname) != "etrial" ]]; then
  echo "You should run this from inside the container."
  exit
fi

key=$(pwgen -1 4 4)
echo $key
mkdir -p ~etrial/crypt
gocryptfs -passfile <(echo $key) -init ~etrial/crypt
gocryptfs -passfile <(echo $key) ~etrial/crypt /crypt
