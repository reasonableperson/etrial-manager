#!/bin/bash

if (( $# != 1 )); then
  echo "Provide the user's full name, in quotes."
  exit
fi

# Create private key.
openssl ecparam -genkey -name secp256r1 | openssl ec -out "$1.key"

# Create CSR.
openssl req -new -key "$1.key" -out "$1.csr" \
  -subj "/C=AU/ST=NSW/L=Sydney/O=CDPP/CN=$1"

# Create certificate using CSR and etrial.ca.key.
openssl x509 -req -days 365 \
  -CA /etc/nginx/etrial.ca.crt -CAkey /etc/nginx/etrial.ca.key -set_serial 0x$(openssl rand -hex 8) \
  -in "$1.csr" -out "$1.crt"

# Create PKCS #12 archive.
openssl pkcs12 -export -inkey "$1.key" -in "$1.crt" -out "$1.pfx"

# Delete unneeded artifacts.
rm "$1.key" "$1.csr"
