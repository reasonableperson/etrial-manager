# Arch environment for cloud SMB host

This document describes a system for hosting a public-facing service that may
have untrusted users from a secure host. It should minimise the risk that poor
administration of the service exposes the host system, while costing less and
delivering better performance than shitty $10/month cloud VMs.

x86 and ARM are too different to make this a Raspberry Pi project. It may be
better simply to deploy this on a laptop. But the techniques should be generally
useful for the Raspberry Pi idea as well.

## Creating the container

    mkdir /var/lib/machines/etrial
    pacstrap -c /var/lib/machines/etrial base \
      entr gunicorn nginx python-toml python-pytz python-flask \
      openssh sshguard \
      vim

Add pts/0 to pts/9 as permissible root login ttys:

    for i in {0..9}; do echo pts/$i >> /var/lib/machines/etrial/etc/securetty; done

Create a MACVLAN interface for the container, and give it access to a location
on your local system:

    >> /etc/systemd/nspawn/etrial.nspawn \
    echo '[Network]
    MACVLAN=eno1
    [Files]
    Bind=/space/etrial:/secure
    Bind=/home/scott/git/etrial:/home/etrial
    PrivateUsers=pick

Start the container and log in:

    machinectl start etrial
    machinectl login etrial
    passwd

Configure the network using DHCP:

    >> /etc/systemd/network/mv-eno1.network echo '[Match]
    Name=mv-eno1
    [Link]
    MACAddress=4a:f0:e5:e2:be:ef
    [Network]
    DHCP=ipv4'
    systemctl enable systemd-networkd systemd-resolved
    systemctl start systemd-networkd systemd-resolved

Lock down SSH:

    >> /etc/ssh/sshd_config echo '
    PasswordAuthentication no
    Match User jury
    ForceCommand internal-sftp
    ChrootDirectory /home/jury
    PermitTunnel no
    AllowAgentForwarding no
    AllowTcpForwarding no
    X11Forwarding no'

Port forward SSH on your router.

# Configure gunicorn

Automatically start the Flask app using Gunicorn on boot:

    useradd etrial

    > /etc/systemd/system/etrial-web.service echo '[Unit]
    Description=Flask etrial app
    After=network.target
    [Service]
    Type=simple
    User=etrial
    WorkingDirectory=/home/etrial
    ExecStart=/usr/bin/gunicorn --access-logfile - --reload \
      --reload-extra-file templates/base.html  \
      --reload-extra-file templates/home.html  \
      --reload-extra-file templates/admin.html  \
      --reload-extra-file templates/log.html  \
      app:app
    KillMode=mixed
    TimeoutStopSec=5
    [Install]
    WantedBy=multi-user.target'

    systemctl enable etrial-web
    systemctl start etrial-web

# Configure nginx

Copy the SSL wildcard certificate from nuclet:

    cp /etc/letsencrypt/live/sjy.id.au/privkey.pem /var/lib/machines/etrial/etc/nginx/sjy.id.au.key
    cp /etc/letsencrypt/live/sjy.id.au/cert.pem /var/lib/machines/etrial/etc/nginx/sjy.id.au.crt
    chown -R vu-etrial-0:vg-etrial-0 /var/lib/machines/etrial/etc/nginx

# HTTPS authentication

In the container, create a CA and move the keyfile and certificate into the
`nginx` configuration directory:

    cd ~etrial
    scripts/create-ca.sh
    mv etrial.ca.* /etc/nginx

Then create a new user and move the certificate into the `certs` directory:

    scripts/add-https-user.sh "Scott Young"
    mv *.crt certs

On nuclet, take ownership of the certificate so you can copy it directly from
the container and import it into Firefox. Then, delete the PFX file.

    sudo chown scott:scott ~scott/git/etrial/"Scott Young.pfx"

# nginx config

    > /etc/nginx.conf echo '
    events { worker_connections 1024; }
    http {
      include mime.types;
      server {
          listen       443 ssl;
          server_name  etrial.sjy.id.au;
          client_max_body_size 4G;
          ssl_certificate        sjy.id.au.crt;
          ssl_certificate_key    sjy.id.au.key;
          ssl_client_certificate etrial.ca.crt;
          ssl_verify_client      on;

          location / {
              proxy_pass   http://127.0.0.1:8000;
              proxy_set_header X-SSL-Client-Certificate $ssl_client_escaped_cert;
          }

          location /static { root /home/etrial; }
          location /docs { root /secure; }
      }
    }'

    systemctl enable nginx
    systemctl start nginx

# Creating SFTP users

    groupadd sftp

Use RSA keys for compatibility with GoodReader:

    useradd jury  -g sftp -s /bin/false
    ssh-keygen -t rsa -m PEM -f jury.sshkey -C jury-$(date -I) -N ''
    mkdir -p /home/jury/.ssh
    ssh-keygen -y -f jury.sshkey > /home/jury/.ssh/authorized_keys
    chown -R jury:sftp /home/jury


    cp /var/lib/machines/etrial/home/jury/.ssh/jury.sshkey ~
    chmod 777 ~/jury.sshkey

    >> /etc/ssh/sshd_config echo 'Match User jury
    ForceCommand internal-sftp
    ChrootDirectory /home/jury
    PermitTunnel no
    AllowAgentForwarding no
    AllowTcpForwarding no
    X11Forwarding no'

    useradd judge -g sftp -s /bin/false




