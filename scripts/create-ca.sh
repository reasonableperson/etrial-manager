#!/bin/bash

set -x

dest=/var/lib/machines/etrial/etc/nginx
openssl ecparam -genkey -name secp256r1 | openssl ec -out $dest/client.ca.key
openssl req -new -x509 -days 3650 -key $dest/client.ca.key -out $dest/client.ca.crt \
  -subj "/C=AU/ST=NSW/L=Sydney/O=CDPP/CN=etrial"
