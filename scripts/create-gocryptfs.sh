#!/bin/bash

if [[ $(</proc/sys/kernel/hostname) != "etrial" ]]; then
  echo "You should run this from inside the container."
  exit
fi

if [[ "$1" == "purge" ]]; then
  fusermount -u /crypt
  rm -rf ~etrial/crypt
fi

key=$(pwgen -1 4 4)
echo $key
mkdir -p ~etrial/crypt
gocryptfs -passfile <(echo $key) -init ~etrial/crypt 2>&1
