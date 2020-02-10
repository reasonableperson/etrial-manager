# etrial-manager

This repository supports a courtroom evidence presentation system consisting of:

* the **etrial manager**, a Flask application that can be used to upload files
  using a web browser and mark them for publication, which can run on a laptop
  or container running Ubuntu, and

* **WebDAV users** using software like [PDF Expert][pdf-expert] on a tablet
  computer such as an iPad, and

[pdf-expert]: https://pdfexpert.com/

* a network allowing the two to communicate -- either a local wireless network,
  or the Internet.

# Server setup

## Laptop connected to wireless access point

Download the [latest LTS release of Ubuntu][ubuntu-dl] (this guide was written
for Ubuntu 18.04.3) and write the ISO to a USB flash drive.

[ubuntu-dl]: https://ubuntu.com/download/desktop

Boot the laptop and follow the prompts in the graphical installer. Be sure to
set up full-disk encryption so that data is protected against theft. When you
have access to a terminal, skip forward to the software section.

## Container connected to the Internet

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

## Software

You've configured a Ubuntu machine, connected it to the internet, and logged
into it using SSH. Here's how to set up the etrial manager software on it.

    apt install /var/lib/etrial/etrial-manager-0.2.0.deb

You should have a file in the current directory called `default.pfx` which can
be imported into your browser to access the web interface which is now running
on the IP address assigned to your container.
