#!/bin/bash

if [[ $(</etc/hostname) != "etrial" ]]; then
  echo "You should run this from inside the container."
  exit
fi

touch /home/etrial/metadata.toml.txt
mkdir /home/etrial/keys
