#!/bin/bash

set -x

userdel judge
userdel jury
userdel witness

rm -r /home/judge /home/jury /home/witness
rm /home/etrial/ssh/*
