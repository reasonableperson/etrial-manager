#!/bin/bash

if (( $# != 4 )); then
  echo "Usage: add-https-user.sh <username> <user-full-name> <ca-crt> <ca-key>"
  exit
fi

# Create private key.
openssl ecparam -genkey -name secp256r1 | openssl ec -out "$1.key"

# Create CSR.
openssl req -new -key "$1.key" -out "$1.csr" \
  -subj "/C=AU/ST=NSW/L=Sydney/O=CDPP/CN=$2"

# Create certificate using CSR and etrial.ca.key.
openssl x509 -req -days 365 -set_serial 0x$(openssl rand -hex 8) \
  -in "$1.csr" -out "$1.crt" -CA "$3" -CAkey "$4"

# Create PKCS #12 archive.
openssl pkcs12 -export -inkey "$1.key" -in "$1.crt" -out "$1.pfx"

# Delete unneeded artifacts.
rm "$1.csr" "$1.key" "$1.crt"
echo "Created TLS certificate bundle $1.pfx."
