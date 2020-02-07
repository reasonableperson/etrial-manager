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

# Design

This software is designed to run in two modes:

* **Internet mode**, in which the application runs on a VM or container running
  Ubuntu Linux, which has ports 80 and 443 exposed to the internet. Because the
  same IP address may be reused to support multiple cases in internet mode,
  multiple instances of the Flask application may be run behind a single nginx
  instance. This option is easier to deploy, but requires a reliable internet
  connection and offers less physical security.

* **Standalone mode**, in which the application runs on a laptop running Ubuntu
  Linux, which also acts as a DHCP server, DNS server and (optionally) Internet
  router using an attached USB LTE modem. Nearby users connect to a wireless
  network broadcast by an attached UniFi AC PRO.

# Security

An earlier version of this software featured encryption support. This was
implemented in order to support deployment on a Raspberry Pi (which would need
to boot into an unencrypted OS without exposing encrypted user data). This added
significant complexity.

The same outcome can be achieved by using a laptop with full disk encryption,
instead of a Raspberry Pi, as the server.
