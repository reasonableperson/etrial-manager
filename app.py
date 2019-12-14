import collections
import datetime
import hashlib
import json
import logging
import os
import subprocess
import urllib

import dateutil.parser
import dateutil.tz
import pytz
import toml
from flask import Flask, flash, g, render_template, redirect, request

# The case-specific state of this app should all be mounted on secure
# encrypted storage which disappears when power is lost (this may indicate
# that the device was stolen).

CODE_DIR = os.path.dirname(os.path.realpath(__file__))
SCRIPT_DIR = os.path.join(CODE_DIR, 'scripts')
ADMIN_DIR = '/home/etrial'
FILES_DIR = '/home/etrial/files'
CLIENT_CERT_DIR = '/home/etrial/https'

# The metadata file is essentially a small database. The logs are also stored
# in plain text and interrogated using basic utilities. Configuring the logger
# here means we also get logs to stdout, which is convenient for debugging
# using systemd utilities. To avoid SD card wear, it may be wise to write
# system-level logs to /tmp and rely on these encrypted, lower-traffic logs as
# the sole audit trail.

METADATA_FILE = os.path.join(ADMIN_DIR, 'metadata.toml.txt')
LOG_FILE = logging.FileHandler(os.path.join(ADMIN_DIR, 'etrial.log.txt'))
logging.basicConfig(level=logging.INFO, handlers=[LOG_FILE, logging.StreamHandler()])

# Now that we've set up some constants that govern our interaction with the
# encrypted volume provided by the host OS, we can set up the Flask app with a
# random secret. TODO: randomly generate this.

app = Flask(__name__)
app.config['SECRET_KEY'] = b'_\xfd\xd9\xe53\x00\x8e\xbc\xa4\x14-\x97\x11\x0e&>'

TZ = pytz.timezone('Australia/Sydney')

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
    for c in os.listdir(CLIENT_CERT_DIR):
        if c[-4:] == '.crt':
            with open(os.path.join(CLIENT_CERT_DIR, c)) as fd:
                if cert == fd.read():
                    return c.replace('.crt', '')

# Send the user a message which is also recorded in the log in JSON format.

def log_silent(msg, level=logging.INFO):
    if type(msg) != dict: msg = {'message': msg}
    logging.log(level, json.dumps(msg))
    return msg

def log_flash(msg, level=logging.INFO):
    flash(log_silent(msg, level), {
        logging.INFO: 'info',
        logging.WARNING: 'warning',
        logging.ERROR: 'error',
    }[level])
    return msg

# Now it's time to define some routes. The home page is just a list of all the
# documents available.

@app.route('/')
def home():
    try:
        load_metadata()
        return redirect('/documents')
    except:
        return "Can't read metadata file. You need to decrypt the secure partition.", 500

@app.route('/documents')
def documents():
    def sydney_time(): return datetime.datetime.now(TZ)
    g.now = sydney_time()

    # handle sort argments
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

    script = [os.path.join(SCRIPT_DIR, 'filtered-journal.sh')]
    stdout = subprocess.run(script, capture_output=True).stdout.decode('utf-8')
    _json = [json.loads(l) for l in stdout.split('\n') if l != '']

    if not request.args.get('reverse') == '': _json.reverse()

    return render_template('log.html', log=_json)

@app.template_filter('strptime')
def template_filter_strptime(iso8601):
    return dateutil.parser.parse(iso8601)

@app.template_filter('strfdate')
def template_filter_strfdate(dt):
    return dt.astimezone(dateutil.tz.tzlocal()).strftime('%a %-d %b')

@app.template_filter('strfdate_long')
def template_filter_strfdate(dt):
    return dt.astimezone(dateutil.tz.tzlocal()).strftime('%a %-d %b %Y')

@app.template_filter('strftime')
def template_filter_strftime(dt):
    return dt.astimezone(dateutil.tz.tzlocal()).strftime('%-I:%M %p').lower()

@app.template_filter('strftime_long')
def template_filter_strftime(dt):
    return dt.astimezone(dateutil.tz.tzlocal()).strftime('%-I:%M:%S %p').lower()

@app.template_filter('strftz')
def template_filter_strftime(dt):
    return dt.astimezone(dateutil.tz.tzlocal()).strftime('%Z')

# The settings page is used to back up the device, add and remove users, and
# perform other administrative tasks.

@app.route('/settings')
def admin():
    metadata = load_metadata()
    user = get_user_name()
    keys = os.listdir(CLIENT_CERT_DIR)
    return render_template('settings.html', keys=keys)

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

# Delete a document from the database. This should be stuck behind a
# confirmation, as it implies recalling the document from the SFTP share.

@app.route('/delete/<_hash>', methods=['POST'])
def delete(_hash):
    metadata = load_metadata()
    user = get_user_name()
    published_to = metadata[_hash].get('published')
    if published_to is None or published_to == []:
        del metadata[_hash]
        msg = log_flash({
            'message': f'Deleted {metadata[_hash].get("title")}.',
            'action': 'delete', 'hash': _hash
        })
        save_metadata(metadata)
        return json.dumps(msg), 200
    else:
        msg = log_flash({
            'message': f"Can't delete {metadata[_hash].get('title')}, it's published to {published_to}.",
            'action': 'delete', 'hash': _hash
        }, level=logging.ERROR)
        return json.dumps(msg), 400

# Add a new document to the database.

@app.route('/upload', methods=['POST'])
def upload():
    metadata = load_metadata()
    user = get_user_name()
    title = request.args.get('filename')
    h = hashlib.blake2b(digest_size=20)
    h.update(request.data)
    _hash = h.hexdigest()
    with open(os.path.join(ADMIN_DIR, 'files', _hash), 'wb') as fd:
        fd.write(request.data)
    metadata[_hash] = { 'title': title, 'added': datetime.datetime.now(TZ) }
    save_metadata(metadata)
    msg = log_flash({
        'message': f'Uploaded {title}.',
        'action': 'upload', 'title': title, 'hash': _hash,
        'size_mb': len(request.data)/10**6
    })
    return msg, 200

def refresh_hardlinks(metadata, user_group):
    user_dir = f'/jails/{user_group}/etrial'
    existing_hardlinks = os.listdir(user_dir)
    for _hash, meta in metadata.items():
        source = os.path.join(FILES_DIR, _hash)
        destination = os.path.join(user_dir, meta['title'])
        if 'published' in meta and user_group in meta['published']:
            if meta['title'] not in existing_hardlinks:
                # These documents have been newly published
                os.link(source, destination)
                log_silent({'action': 'link', 'source': source, 'destination': destination})
        # These documents have been newly recalled
        elif meta['title'] in existing_hardlinks:
            os.remove(destination)
            log_silent({'action': 'unlink', 'destination': destination})

# Publish a document to the specified user group.

@app.route('/publish/<_hash>/<user_group>', methods=['POST'])
def publish(_hash, user_group):
    metadata = load_metadata()
    doc = metadata[_hash]
    msg = log_flash({
        'message': f'Published {doc["title"]} to {user_group}.',
        'action': 'publish', 'hash': _hash, 'title': doc['title'],
        'user_group': user_group
    })
    if 'published' not in metadata[_hash]: metadata[_hash]['published'] = []
    metadata[_hash]['published'].append(user_group)
    refresh_hardlinks(metadata, user_group)
    save_metadata(metadata)
    return msg, 200

@app.route('/recall/<_hash>/<user_group>', methods=['POST'])
def recall(_hash, user_group):
    metadata = load_metadata()
    doc = metadata[_hash]
    msg = log_flash({
        'message': f'Recalled {doc["title"]} from {user_group}.',
        'action': 'recall', 'hash': _hash, 'title': doc['title'],
        'user_group': user_group
    }, logging.WARNING)
    metadata[_hash]['published'].remove(user_group)
    refresh_hardlinks(metadata, user_group)
    save_metadata(metadata)
    return msg, 200
