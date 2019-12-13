#!/bin/bash

if [[ $(</proc/sys/kernel/hostname) != "etrial" ]]; then
  echo "You should run this from inside the container."
  exit
fi

touch /home/etrial/metadata.toml.txt
mkdir /home/etrial/keys

for class in judge jury witness; do
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
  mkdir -p /jails/$class/dev/journal
  echo "/run/systemd/journal /jails/$class/dev/journal non bind 0 0" >> /etc/fstab
  ln -s journal/dev-log /jails/$class/dev/log
  chown etrial:$class /jails/$class/etrial
done
mount -a
