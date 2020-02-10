# Server configuration guide

## Laptop configuration

Download the [latest LTS release of Ubuntu][ubuntu-dl] (this guide was written
for Ubuntu 18.04.3) and write the ISO to a USB flash drive.

[ubuntu-dl]: https://ubuntu.com/download/desktop

Boot the laptop and follow the prompts in the graphical installer. Be sure to
set up full-disk encryption so that data is protected against theft.

## Container configuration

It is assumed that you are already running a DHCP server which can configure
the container's network interface based on a known MAC address
(`4a:f0:e5:e2:be:ef`) and expose ports 80 and 443 to the internet.

[1]: https://wiki.archlinux.org/index.php/Systemd-nspawn#Create_a_Debian_or_Ubuntu_environment

Create a new Ubuntu container called `etrial`:

    cd /var/lib/machines
    mkdir etrial
    debootstrap --components=main,universe bionic etrial http://au.archive.ubuntu.com/ubuntu/

Set the container's hostname:

    echo etrial > /var/lib/machines/etrial/etc/hostname

Set the container's network interface's MAC address to `4a:f0:e5:e2:be:ef` and
configure the interface with DHCP:

    echo '[Match]
    Name=mv-eno1
    [Link]
    MACAddress=4a:f0:e5:e2:be:ef
    [Network]
    DHCP=ipv4' > /var/lib/machines/etrial/etc/systemd/network
    ln -s /usr/lib/systemd/system/systemd-networkd.service \
      /var/lib/machines/etrial/etc/systemd/system/multi-user.target.wants/systemd-networkd.service

Make sure the container actually has a MACVLAN network interface, and give it
access to this repository for convenience:az

    echo ' [Service]
    ExecStart=
    ExecStart=/usr/bin/systemd-nspawn --keep-unit --boot --machine=etrial \
        --bind-ro=/home/scott/git/etrial:/var/lib/etrial --network-macvlan=eno1
    ' > /etc/systemd/system/systemd-nspawn@etrial.service.d/macvlan.conf

Enable the container so it starts on boot:

    systemctl enable systemd-nspawn@etrial
    systemctl start systemd-nspawn@etrial

Open a shell:

    machinectl shell root@etrial
