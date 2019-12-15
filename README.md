# etrial-manager

This repository contains a Flask application and a series of configuration
files and shell scripts for configuring a companion nginx instance to proxy the
application for authorised administrators, and an OpenSSH daemon which provides
audited access to file shares configured using the Flask application over SFTP.

Collectively, these files constitute an open source framework for presenting
information in the context of an electronic criminal trial. The framework has
been designed to meet the transparency and security requirements of real
court proceedings. The system can be deployed either in a container on an
internet-connected host server running Arch Linux, or on a Raspberry Pi
connected to a local wireless network in the courtroom itself.

# Container-based installation

First, create a a new directory on your host system and use `pacstrap` to
install Arch Linux in it along with `etrial-manager`'s dependencies:

    CONTAINER_ROOT=/var/lib/machines/etrial
    mkdir -p $CONTAINER_ROOT/crypt
    pacstrap -c $CONTAINER_ROOT base \
      nginx gocryptfs gunicorn man openssh sshguard pwgen vim \
      python-dateutil python-flask python-toml

Now, create a drop-in folder for the `systemd-nspawn` template unit (this
should already be installed if you use a recent version of `systemd`). Put
`config/nspawn-etrial.service.conf` in there to give your container a MACVLAN
interface, disable user namespacing, and give it access to the host OS's FUSE
module. (We need to use a service, rather than just invoking the container
directly with `systemd-nspawn` or `machinectl`, so that we can use the
`DeviceAllow=` directive and ensure that the container starts up with the host.)

    HOST_SYSTEMD_DIR=/etc/systemd
    REPO_DIR=~scott/git/etrial
    mkdir -p $HOST_SYSTEMD_DIR/system/systemd-nspawn@etrial.service.d
    ln -s $REPO_DIR/config/nspawn-etrial.service.conf \
      $HOST_SYSTEMD_DIR/system/systemd-nspawn@etrial.service.d

Configure the container's network interface with the custom MAC address
`4a:f0:e5:e2:be:ef`, and configure it to ask your local DHCP server for an IP
and DNS resolver:

    cp $REPO_DIR/config/mv-eno1.network $CONTAINER_ROOT/etc/systemd/network
    ln -s /usr/lib/systemd/system/systemd-networkd.service \
      $CONTAINER_ROOT/etc/systemd/system/multi-user.target.wants/systemd-networkd.service
    ln -s /usr/lib/systemd/system/systemd-resolved.service \
      $CONTAINER_ROOT/etc/systemd/system/multi-user.target.wants/systemd-resolved.service

Configure the container's sshd config to disable almost everything, listen on
a custom port, and lock SFTP users into a chroot jail:

    cp $REPO_DIR/config/sshd_config $CONTAINER_ROOT/etc/ssh
    ln -s /usr/lib/systemd/system/sshd.service \
      $CONTAINER_ROOT/etc/systemd/system/multi-user.target.wants/sshd.service

Install and enable the gunicorn service:

    cp $REPO_DIR/config/gunicorn.service /var/lib/machines/etrial/etc/systemd/system
    ln -s /etc/systemd/system/gunicorn.service \
      $CONTAINER_ROOT/etc/systemd/system/multi-user.target.wants/gunicorn.service

Configure nginx, locking it down to users with a valid client certificate only,
and generate a certificate bundle to bootstrap your access to the web interface:

    $REPO_DIR/scripts/configure-nginx.sh \
      /etc/letsencrypt/live/sjy.id.au/privkey.pem \
      /etc/letsencrypt/live/sjy.id.au/cert.pem \
      $CONTAINER_ROOT/etc/nginx

Enable the container to ensure that it automatically starts on the next reboot,
and start it immediately:

    systemctl enable systemd-nspawn@etrial
    systemctl start systemd-nspawn@etrial

You should have a file in the current directory called `scott.crt` which can
be imported into your browser to access the web interface which is now running
on the IP address assigned to your container.

You'll also have `client.key`, which is the CA key used to authorise new HTTP
users. If you don't plan on adding any other administrators, simply delete it.
Otherwise, once you've created an encrypted volume in the web app, upload
`client.key` to enable this functionality. (It would be unsafe to leave this
key on the cleartext filesystem we have set up so far.)

## Troubleshooting

If you want a shell on the container, run the following on the host:

    for i in {0..9}; do echo pts/$i >> /var/lib/machines/etrial/etc/securetty; done
    machinectl shell root@etrial
