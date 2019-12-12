#!/bin/bash

if (( $# != 2 )); then
  echo "You must provide an identity name (eg. juror1) and a permission group (Linux user, eg. jury)."
  exit
fi

identity=$1
group=$2
keyfile=/secure/keys/$identity.ssh.txt
echo Creating new SSH key for identity "'"$identity"'" in permission group "'"$group"'".

cd /secure/keys
ssh-keygen -t rsa -m PEM -f $keyfile -C $identity-$(date -I) -N ''
ssh-keygen -y -f $keyfile >> /secure/$group/.ssh/authorized_keys
chmod 666 $keyfile
