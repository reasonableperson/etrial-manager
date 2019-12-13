#!/bin/bash

if (( $# != 2 )); then
  echo "You must provide an identifier (eg. juror1) and a username (eg. jury)."
  exit
fi

identity=$1
class=$2
mkdir -p /home/etrial/ssh
keyfile=/home/etrial/ssh/$identity.$class.key.txt

if [[ ! -d /home/$class ]]; then
  echo Creating new Unix user for class $class.
  useradd -m $class
  echo Disabling password authentication.
  usermod -p '*' $class
  mkdir /home/$class/.ssh
  touch /home/$class/.ssh/authorized_keys
  chown $class:$class -R /home/$class/.ssh
  chmod 700 /home/$class/.ssh
  # The chroot has to be located in a directory owned by root, so /home is
  # not suitable. Conveniently, using this location means that backing up all
  # of /home won't produce duplicate copies, because it won't see the hardlinks
  # in these SFTP chroots.
  mkdir -p /jails/$class/etrial
  chown etrial:$class /jails/$class/etrial
fi

echo Creating new SSH key for identity "'"$identity"'" with class "'"$class"'".
ssh-keygen -t rsa -m PEM -f $keyfile -C $identity-$(date -I) -N ''

echo Authorising SSH key to log in as $class.
cat $keyfile.pub >> /home/$class/.ssh/authorized_keys
chmod 600 /home/$class/.ssh/authorized_keys
rm $keyfile.pub
