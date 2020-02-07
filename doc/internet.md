# Internet server configuration guide

Create a new Ubuntu container:

    cd /var/lib/machines
    mkdir ligar
    debootstrap --include=systemd-container --components=main,universe bionic ligar http://au.archive.ubuntu.com/ubuntu/
    machinectl start ligar

Log into the container and install dependencies:

    machinectl shell root@ligar

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

    ln -s /var/lib/etrial/config/macvlan.network \
      $CONTAINER_ROOT/etc/systemd/network
    ln -s /usr/lib/systemd/system/systemd-networkd.service \
      $CONTAINER_ROOT/etc/systemd/system/multi-user.target.wants/systemd-networkd.service
    ln -s /usr/lib/systemd/system/systemd-resolved.service \
      $CONTAINER_ROOT/etc/systemd/system/multi-user.target.wants/systemd-resolved.service

## Troubleshooting

If you want a shell on the container, run the following on the host:

    for i in {0..9}; do echo pts/$i >> /var/lib/machines/etrial/etc/securetty; done
    machinectl shell root@etrial
The same outcome can be achieved by using a laptop with full disk encryption,
instead of a Raspberry Pi, as the server.
