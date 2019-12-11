#!/bin/bash

openssl ecparam -genkey -name secp256r1 | openssl ec -out etrial.ca.key
openssl req -new -x509 -days 3650 -key etrial.ca.key -out etrial.ca.crt \
  -subj "/C=AU/ST=NSW/L=Sydney/O=CDPP/CN=etrial"
