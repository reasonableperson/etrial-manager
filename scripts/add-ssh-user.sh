#!/bin/bash

if (( $# != 2 )); then
  echo "You must provide an identifier (eg. juror1) and a username (eg. jury)."
  exit
fi

identity=$1
class=$2
mkdir -p /home/etrial/ssh
keyfile=/home/etrial/ssh/$identity.$class.key.txt

echo Creating new SSH key for identity "'"$identity"'" with class "'"$class"'".
ssh-keygen -t rsa -m PEM -f $keyfile -C $identity-$(date -I) -N ''

echo Authorising SSH key to log in as $class.
cat $keyfile.pub >> /home/$class/.ssh/authorized_keys
chmod 600 /home/$class/.ssh/authorized_keys
rm $keyfile.pub
