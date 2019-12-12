import collections
import datetime
import hashlib
import logging
import os
import pytz
import urllib

import toml
from flask import Flask, flash, g, render_template, redirect, request

# The case-specific state of this app should all be mounted on secure
# encrypted storage which disappears when power is lost (this may indicate
# that the device was stolen).

CRYPT_ROOT = '/secure/'
FILES_DIR = os.path.join(CRYPT_ROOT, 'files')
CERTS_DIR = os.path.join(CRYPT_ROOT, 'certs')

# The metadata file is essentially a small database. The logs are also stored
# in plain text and interrogated using basic utilities. Configuring the logger
# here means we also get logs to stdout, which is convenient for debugging
# using systemd utilities. To avoid SD card wear, it may be wise to write
# system-level logs to /tmp and rely on these encrypted, lower-traffic logs as
# the sole audit trail.

METADATA_FILE = os.path.join(CRYPT_ROOT, 'metadata.toml.txt')
LOG_FILE = logging.FileHandler(os.path.join(CRYPT_ROOT, 'etrial.log.txt'))
logging.basicConfig(level=logging.INFO, handlers=[LOG_FILE, logging.StreamHandler()])

# Now that we've set up some constants that govern our interaction with the
# encrypted volume provided by the host OS, we can set up the Flask app with a
# random secret. TODO: randomly generate this.

app = Flask(__name__)
app.config['SECRET_KEY'] = b'_\xfd\xd9\xe53\x00\x8e\xbc\xa4\x14-\x97\x11\x0e&>'

def sydney_time(): return datetime.datetime.now(pytz.timezone('Australia/Sydney'))

# These functions load and dump the database to a TOML file. Performance isn't
# really much of an issue since we rarely would have as much as 1 MB of data.
# Using a TOML file means that Windows users can easily inspect and edit the
# database using Notepad.

def load_metadata():
    with open(METADATA_FILE) as fd:
        return toml.load(fd)

def save_metadata(md):
    with open(METADATA_FILE, 'w') as fd:
        return toml.dump(md, fd)

# Authentication is managed using HTTP client certificates, so it is stateless
# from Flask's perspective. This function runs on every page load and compares
# the certificate forwarded by nginx to the certificates authorised for use in
# this particular case.

def get_user_name():
    cert = urllib.parse.unquote(request.headers.get('X-Ssl-Client-Certificate'))
    for c in os.listdir(CERTS_DIR):
        with open(os.path.join(CERTS_DIR, c)) as fd:
            if cert == fd.read():
                return c.replace('.crt', '')

# Now it's time to define some routes. The home page is just a list of all the
# documents available.

@app.route('/')
def home():
    return redirect('/documents')

@app.route('/documents')
def documents():
    g.now = sydney_time()
    sort = { 'field': request.args.get('sort'), 'reverse': request.args.get('reverse') }
    if sort['field'] not in ['added', 'identifier', 'title']:
        if sort['field'] is not None: return redirect('/documents')
        else: sort['field'] = 'added'
    sort['reverse'] = sort['reverse'] == ''
    sort_key = (lambda field: lambda pair: pair[1].get(field) or '')(sort['field'])
    metadata = sorted(load_metadata().items(), key=sort_key, reverse=sort['reverse'])
    user = get_user_name()
    return render_template('documents.html', metadata=metadata, user=user, sort=sort)

# The log page provides tools for inspecting this application's own logs, stored
# on the encrypted partition.

@app.route('/log')
def log():
    metadata = load_metadata()
    user = get_user_name()
    return render_template('log.html')

# The settings page is used to back up the device, add and remove users, and
# perform other administrative tasks.

@app.route('/settings')
def admin():
    metadata = load_metadata()
    user = get_user_name()
    certs = os.listdir(CERTS_DIR)
    return render_template('settings.html', certs=certs)

# The remaining routes all define commands of some sort. This one is used to
# create a new administrative user. It generates an HTTPS certificate bundle
# for them.

@app.route('/create/admin-user', methods=['POST'])
def create_admin_user():
    if request.form.get('name') == '':
        return redirect('/settings')
    else:
        return 'ok'

# This one creates an SSH key for an iPad user.

@app.route('/create/limited-user', methods=['POST'])
def create_limited_user():
    if request.form.get('name') == '':
        return redirect('/settings')
    else:
        return 'ok'

# Given the hash of a document, try to guess what the user would like to name
# it and assign an identifier automatically.

@app.route('/identify/<_hash>/<prefix>', methods=['POST'])
def identify(_hash, prefix):
    metadata = load_metadata()
    user = get_user_name()
    logging.info(_hash, prefix)
    existing_identifiers = [d.replace(prefix, '') for d in metadata.values() if d.get('id') is not None and d.get('id')[:len(prefix)] == prefix]
    logging.info('existing ids:', existing_identifiers)
    metadata[_hash].update({ 'identifier': f'{prefix} 1' })
    save_metadata(metadata)
    return 'ok'

# Delete a document from the database. This should be stuck behind a
# confirmation, as it implies recalling the document from the SFTP share.

@app.route('/delete/<_hash>', methods=['POST'])
def delete(_hash):
    metadata = load_metadata()
    user = get_user_name()
    del metadata[_hash]
    save_metadata(metadata)
    return 'ok'

# Add a new document to the database.

@app.route('/upload', methods=['POST'])
def upload():
    metadata = load_metadata()
    user = get_user_name()
    logging.info(f'Received {len(request.data)} bytes.')
    title = request.args.get('filename')
    h = hashlib.blake2b(digest_size=20)
    h.update(request.data)
    _hash = h.hexdigest()
    with open(os.path.join(CRYPT_ROOT, 'files', _hash), 'wb') as fd:
        fd.write(request.data)
    metadata[_hash] = { 'title': title, 'added': datetime.datetime.now(pytz.timezone('Australia/Sydney')) }
    save_metadata(metadata)
    return 'Thanks.'

def refresh_hardlinks(metadata, user_group):
    user_dir = os.path.join(CRYPT_ROOT, user_group)
    existing_hardlinks = os.listdir(user_dir)
    for _hash, meta in metadata.values():
        if user_group in meta.published:
            source = os.path.join(FILES_DIR, _hash)
            destination = os.path.join(user_dir, meta.title)
            # These documents have been newly published
            if destination not in existing_hardlinks:
                os.link(source, destination)
                existing_hardlinks.remove(destination)
                logging.info(f'Linked {_hash} to {destination}.')
        # These documents have been newly recalled
        elif destination in existing_hardlinks:
            os.remove(destination)
            logging.info(f'Removed link from {_hash} to {destination}.')

# Publish a document to the specified user group.

@app.route('/publish/<_hash>/<user_group>', methods=['POST'])
def publish(_hash, user_group):
    metadata = load_metadata()
    doc = metadata[_hash]
    logging.info(f'Publishing {_hash} ({doc["title"]}) to user_group {user_group}.')
    if 'published' not in metadata[_hash]: metadata[_hash]['published'] = []
    metadata[_hash]['published'].append(user_group)
    save_metadata(metadata)
    return 'yo'

@app.route('/recall/<_hash>/<user_group>', methods=['POST'])
def recall(_hash, user_group):
    metadata = load_metadata()
    doc = metadata[_hash]
    logging.info(f'Recalling {_hash} ({doc["title"]}) from user_group {user_group}.')
    metadata[_hash]['published'].remove(user_group)
    save_metadata(metadata)
    return 'yo'
