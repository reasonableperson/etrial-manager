#!/bin/bash

set -x

cp /etc/nginx/nginx.conf /home/etrial/config
cp /etc/systemd/system/etrial-web.service /home/etrial/config
cp /etc/ssh/sshd_config /home/etrial/config
