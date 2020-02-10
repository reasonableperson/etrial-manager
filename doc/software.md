# etrial manager setup guide

You've configured a Ubuntu machine, connected it to the internet, and logged
into it using SSH. Here's how to set up the etrial manager software on it.

First, install the latest release of `etrial-manager`, which will install
`nginx` and other dependencies:

    apt install /var/lib/etrial/etrial-manager-0.2.0.deb

Then, add the certbot repository (because the version of certbot packaged in
Ubuntu LTS is too old), install `python-certbot-nginx`, and run it to enable
HTTPS:

    apt-get update
    apt-get install software-properties-common
    add-apt-repository ppa:certbot/certbot
    apt-get update
    apt-get install python-certbot-nginx

    certbot -n --nginx --domains demo.court.digital \
      --agree-tos --email <your_email>


Install some dependencies:


-      nginx gocryptfs gunicorn jq man openssh sshguard pwgen vim \
-      python-dateutil python-flask python-toml

Configure the container's sshd config to disable almost everything, listen on
a custom port, and lock SFTP users into a chroot jail:

    mkdir $CONTAINER_ROOT/etc/systemd/system/sshd.service.d
    ln -s /var/lib/etrial/config/sshd.service.d.conf \
      $CONTAINER_ROOT/etc/systemd/system/sshd.service.d/require-gocryptfs.conf

Configure the encrypted filesystem service:

    ln -s /var/lib/etrial/config/gocryptfs.path \
      $CONTAINER_ROOT/etc/systemd/system/gocryptfs.path
    ln -s /etc/systemd/system/gocryptfs.path \
      $CONTAINER_ROOT/etc/systemd/system/multi-user.target.wants/gocryptfs.path
    ln -s /var/lib/etrial/config/gocryptfs.service \
      $CONTAINER_ROOT/etc/systemd/system/gocryptfs.service

Install and enable the gunicorn service:

    ln -s /var/lib/etrial/config/gunicorn.service \
      $CONTAINER_ROOT/etc/systemd/system/gunicorn.service
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

You should have a file in the current directory called `scott.pfx` which can
be imported into your browser to access the web interface which is now running
on the IP address assigned to your container.

You'll also have `client.key`, which is the CA key used to authorise new HTTP
users. If you don't plan on adding any other administrators, simply delete it.
Otherwise, once you've created an encrypted volume in the web app, upload
`client.key` to enable this functionality. (It would be unsafe to leave this
key on the cleartext filesystem we have set up so far.)
