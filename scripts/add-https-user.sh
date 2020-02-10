#!/bin/bash

if (( $# != 3 )); then
  echo "Usage: add-https-user.sh <username> <user-full-name> <working-dir>"
  exit 1
fi

cd "$3"
echo "Creating new HTTP user in working directory $3."

# Create private key.
openssl ecparam -genkey -name secp256r1 | openssl ec -out "$1.key"
rc=$?; if [[ $rc != 0 ]]; then exit $rc; fi

# Create CSR.
openssl req -new -key "$1.key" -out "$1.csr" \
  -subj "/C=AU/ST=NSW/L=Sydney/O=CDPP/CN=$2"
rc=$?; if [[ $rc != 0 ]]; then exit $rc; fi

# Create certificate using CSR and <ca-key>.
openssl x509 -req -days 365 -set_serial 0x$(openssl rand -hex 8) \
  -in "$1.csr" -out "$1.crt" -CA /etc/nginx/client.crt -CAkey /etc/nginx/client.key
rc=$?; if [[ $rc != 0 ]]; then exit $rc; fi

# Create PKCS #12 archive.
export_password=$(pwgen -1)
openssl pkcs12 -export -inkey "$1.key" -in "$1.crt" -out "$1.pfx" \
  -password "pass:$export_password"
rc=$?; if [[ $rc != 0 ]]; then exit $rc; fi

# Make the PKCS #12 archive world-readable. That sounds like a terrible idea,
# and generally it would be, but in this case it is necessary to allow the web
# server to serve the key to an existing administrator.
chmod o+r "$1.pfx"

echo "[$1]
real_name = \"$2\"
cert = \"$1.pfx\"
passphrase = \"$export_password\"
seen = $(date -Iseconds)
added = $(date -Iseconds)" >> /home/etrial/users.toml.txt

# Delete unneeded artifacts.
rm "$1.csr" "$1.key" "$1.crt"
echo "Created TLS certificate bundle $1.pfx in $(pwd)."
echo "The certificate bundle was encrypted with the following password:"
echo $export_password
