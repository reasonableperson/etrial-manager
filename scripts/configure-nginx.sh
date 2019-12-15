#!/bin/bash

if [[ $(</proc/sys/kernel/hostname) == "etrial" ]]; then
  echo "You should run this from inside the host."
  exit
fi

if (( $# != 3 )); then
  echo "Usage: configure-nginx.sh <ssl-key-path> <ssl-cert-path> <nginx-config-path>"
  exit
fi

echo "Creating new CA ..."
openssl ecparam -genkey -name secp256r1 | openssl ec -out client.key

subj="/C=AU/ST=NSW/L=Sydney/O=CDPP/CN=etrial"
echo "Creating new server certificate with subject $subj ..."
openssl req -new -x509 -days 3650 -subj $subj -key client.key -out client.crt

echo "Copying client certificate to $3/client.crt ..."
cp client.crt "$3"

echo "Copying HTTPS key from $1 to $3/https.key ..."
cp "$1" "$3/https.key"
echo "Copying HTTPS certificate from $2 to $3/https.crt ..."
cp "$2" "$3/https.crt"

config="$(dirname "$0")/../config/nginx.conf"
echo "Copying nginx config from $config to $3/nginx.conf ... "
cp "$config" "$3/nginx.conf"

echo "Configuring initial user ..."
$(dirname "$0")/add-https-user.sh scott "Scott Young" client.crt client.key && rm client.crt
