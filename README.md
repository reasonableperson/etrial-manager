TODO you can't publish documents, and you don't get an error message, when
an SSH key hasn't been generated for that user group yet.

# Arch environment for cloud SMB host

This document describes a system for hosting a public-facing service that may
have untrusted users from a secure host. It should minimise the risk that poor
administration of the service exposes the host system, while costing less and
delivering better performance than shitty $10/month cloud VMs.

x86 and ARM are too different to make this a Raspberry Pi project. It may be
better simply to deploy this on a laptop. But the techniques should be generally
useful for the Raspberry Pi idea as well.

# Create a virtual server to run the etrial software

On the host OS, create a filesystem that will host the base OS. This filesystem
will be unencrypted and will need to get as far as booting our web application,
allowing the user to supply the key to decrypt `/home`.

This command will create a `systemd-nspawn` container called `etrial`, with an
unconfigured MACVLAN network interface, and a read-only binding for
`/var/lib/etrial`. The `systemd-nspawn` `PrivateUsers=pick` option is used to
enhance security.

For now, it also mounts `/home` for convenience but this needs to be replaced
with an encrypted volume. The bound `/home` directory must be owned by the
container's root user: `chown vu-etrial-0:vg-etrial-0 /home/scott/work/etrial-demo`.

    mkdir /var/lib/machines/etrial
    cp config/etrial.nspawn /etc/systemd/nspawn

Bootstrap the OS:

    pacstrap -c /var/lib/machines/etrial base \
      nginx gunicorn python-dateutil python-flask python-toml python-pytz \
      openssh sshguard \
      exa git vim

Configure the container's network interface with the custom MAC address
`4a:f0:e5:e2:be:ef`, and configure it to ask your local DHCP server for an IP:

    cp config/mv-eno1.network /var/lib/machines/etrial/etc/systemd/network
    ln -s /var/lib/machines/etrial/usr/lib/systemd/system/systemd-networkd.service \
      /var/lib/machines/etrial/etc/systemd/system/multi-user.target.wants/systemd-networkd.service
    ln -s /usr/lib/systemd/system/systemd-resolved.service \
      /var/lib/machines/etrial/etc/systemd/system/multi-user.target.wants/systemd-resolved.service

Copy sshd config and enable sshd service:

    cp config/sshd_config /var/lib/machines/etrial/etc/ssh
    ln -s /usr/lib/systemd/system/sshd.service \
      /var/lib/machines/etrial/etc/systemd/system/multi-user.target.wants/sshd.service

Copy and generate nginx config:

    scripts/create-ca.sh
    cp config/nginx.conf /var/lib/machines/etrial/etc/nginx
    cp /etc/letsencrypt/live/sjy.id.au/privkey.pem /var/lib/machines/etrial/etc/nginx/sjy.id.au.key
    cp /etc/letsencrypt/live/sjy.id.au/cert.pem /var/lib/machines/etrial/etc/nginx/sjy.id.au.crt

Install and enable the gunicorn service:

    cp config/gunicorn.service /var/lib/machines/etrial/etc/systemd/system
    ln -s /var/lib/machines/etrial/etc/systemd/system/gunicorn.service \
      /var/lib/machines/etrial/etc/systemd/system/multi-user.target.wants/gunicorn.service

Allow a 'backdoor' login from the host using `machinectl login`, so that you
can get an HTTPS certificate later:

    for i in {0..9}; do echo pts/$i >> /var/lib/machines/etrial/etc/securetty; done

This should get you to a fully configured nginx instance which you can reach
on port 443.

    machinectl start etrial

# Add HTTPS user

Since you have root access on the host OS, you can get a root shell in the
container and generate a client certificate for yourself that way:

    machinectl login etrial

Generate a new private key and certificate for the user, sign the certificate
using the CA you generated earlier (the credentials were saved in
`/etc/nginx/client.ca.key`), and produce a `.pfx` file in the current directory
(`/root`). The script is interactive; you'll get a chance to set a passphrase
if you intend to send the certificate bundle over an insecure channel.

    /var/lib/etrial/scripts/add-https-user.sh "Scott Young"

There is a handy script for creating a local copy of the certificate in
`/home/scott/git/etrial` with normal permissions (ie. not owned by a container
user).

    scripts/pull-https-cert.sh

# Creating SFTP users

Now that you're in the web interface, you can generate an SSH key. This is
required in order to publish to users holding that SSH key.

This script will generate an SSH key for the specified class (judge, jury or
witness), and create the required Unix account as well if it doesn't exist
already. It uses RSA keys because compatibility with ed25519 is pretty poor
among iOS apps.

    /var/lib/etrial/scripts/add-ssh-user.sh test1 jury

After running it, rather than downloading the key from the web interface you
can fetch it using `scripts/pull-ssh-key.sh`.
