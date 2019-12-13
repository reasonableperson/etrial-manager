#!/bin/bash

if (( $# != 1 )); then
  echo "Provide the user's full name, in quotes."
  exit
fi

mkdir -p /home/etrial/https

# Create private key.
openssl ecparam -genkey -name secp256r1 | openssl ec -out "$1.key"

# Create CSR.
openssl req -new -key "$1.key" -out "$1.csr" \
  -subj "/C=AU/ST=NSW/L=Sydney/O=CDPP/CN=$1"

# Create certificate using CSR and etrial.ca.key.
openssl x509 -req -days 365 \
  -CA /etc/nginx/client.ca.crt -CAkey /etc/nginx/client.ca.key \
  -set_serial 0x$(openssl rand -hex 8) \
  -in "$1.csr" -out "/home/etrial/https/$1.crt"

# Create PKCS #12 archive.
openssl pkcs12 -export -inkey "$1.key" -in "/home/etrial/https/$1.crt" \
  -out "/home/etrial/https/$1.pfx"

chown etrial:etrial -R /home/etrial/https

# Delete unneeded artifacts.
rm "$1.csr" "$1.key"
