#!/bin/bash

if [[ $(</proc/sys/kernel/hostname) != "etrial" ]]; then
  echo "You should run this from inside the container."
  exit 1
fi

if [[ $(whoami) != "etrial" ]]; then
  echo "You should run this as the etrial user so that the resulting data is owned by the correct user."
  exit 1
fi

if [[ "$1" == "purge" ]]; then
  # echo "Purging ..."
  fusermount -u /crypt
  rm -rf ~etrial/crypt
fi

if [ -d ~etrial/crypt ]; then
  # echo "~etrial/crypt already exists; refusing to proceed."
  exit 1
else
  key=$(pwgen -1 4 4)
  echo $key
  mkdir -p ~etrial/crypt
  gocryptfs -passfile <(echo $key) -init ~etrial/crypt 2>&1
fi

