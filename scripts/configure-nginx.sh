#!/bin/bash

# Script run as part of the etrial OS installation / configuration process. It
# generates a custom CA which is used (only) to sign HTTPS client certificates
# and secure the web interface. The script expects to receive the path to a
# local copy of a regular (eg. Let's Encrypt) SSL key and certificate, as well
# as the path to the container's nginx configuration directory (eg.
# /var/lib/machines/etrial/etc/nginx).

if [[ $(</proc/sys/kernel/hostname) == "etrial" ]]; then
  echo "You should run this from the host, not the container."
  exit
fi

if (( $# != 3 )); then
  echo "Usage: configure-nginx.sh <ssl-key-path> <ssl-cert-path> <container-root>"
  exit
fi

CREDS_TMP_DIR="$3/tmp"
ETC_NGINX="$3/etc/nginx"

# The server needs to be a custom CA so it can sign HTTPS client certificates.
# These will be presented by users in order to access the web interface.

echo "Creating new CA ..."
openssl ecparam -genkey -name secp256r1 | openssl ec -out client.key

# Creating this copy of the CA key seems insecure, because inside the container,
# $CREDS_TMP_DIR is not encrypted on disk. The server must be able to read the CA
# key to create HTTPS users. It would be better to store it in /crypt, and we
# can move it there later, but there's no marginal loss of security here,
# because an attacker with physical access could also just disable HTTPS. The
# attacker should still be prevented from mounting /crypt.

echo "Copying CA key to $CREDS_TMP_DIR/client.key ..."
cp client.key "$CREDS_TMP_DIR"

# The server certificate must be stored in /etc/nginx. nginx presents this when
# users attempt to connect. client.crt is a certificate stored on the server
# and used for the purpose of HTTPS client authentication.

subj="/C=AU/ST=NSW/L=Sydney/O=CDPP/CN=etrial"
echo "Creating new server certificate with subject $subj ..."
openssl req -new -x509 -days 3650 -subj $subj -key client.key -out client.crt
echo "Copying client certificate to $ETC_NGINX/client.crt ..."
cp client.crt "$ETC_NGINX"
cp client.crt "$CREDS_TMP_DIR"

# Now we deal with the Let's Encrypt certificate.

echo "Copying HTTPS key from $1 to $ETC_NGINX/https.key ..."
cp "$1" "$ETC_NGINX/https.key"
echo "Copying HTTPS certificate from $2 to $ETC_NGINX/https.crt ..."
cp "$2" "$ETC_NGINX/https.crt"

# Copy the nginx configuration file from the etrial Git repository to the
# container's /etc/nginx.

config="$(dirname "$0")/../config/nginx.conf"
echo "Copying nginx config from $config to $ETC_NGINX/nginx.conf ... "
cp "$config" "$ETC_NGINX/nginx.conf"

# Call another script for bootstrapping the next user.

echo "Configuring initial user ..."
$(dirname "$0")/add-https-user.sh admin "Default Administrator" client.crt client.key && rm client.crt
