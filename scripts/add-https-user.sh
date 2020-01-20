#!/bin/bash

if (( $# != 5 )); then
  echo "Usage: add-https-user.sh <username> <user-full-name> <ca-crt> <ca-key> <working-dir>"
  exit 1
fi

cd "$5"
echo "Creating new HTTP user in working directory $5."

# Create private key.
openssl ecparam -genkey -name secp256r1 | openssl ec -out "$1.key"
rc=$?; if [[ $rc != 0 ]]; then exit $rc; fi

# Create CSR.
openssl req -new -key "$1.key" -out "$1.csr" \
  -subj "/C=AU/ST=NSW/L=Sydney/O=CDPP/CN=$2"
rc=$?; if [[ $rc != 0 ]]; then exit $rc; fi

# Create certificate using CSR and <ca-key>.
openssl x509 -req -days 365 -set_serial 0x$(openssl rand -hex 8) \
  -in "$1.csr" -out "$1.crt" -CA "$3" -CAkey "$4"
rc=$?; if [[ $rc != 0 ]]; then exit $rc; fi

# Create PKCS #12 archive.
export_password=$(pwgen -1)
openssl pkcs12 -export -inkey "$1.key" -in "$1.crt" -out "$1.pfx" \
  -password "pass:$export_password"
rc=$?; if [[ $rc != 0 ]]; then exit $rc; fi

# Delete unneeded artifacts.
rm "$1.csr" "$1.key" "$1.crt"
echo "Created TLS certificate bundle $1.pfx in $(pwd)."
echo "The certificate bundle was encrypted with the following password:"
echo -n $export_password
