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
import toml
from flask import Flask, flash, g, render_template, redirect, request

# Configuration

CODE_ROOT = os.path.dirname(os.path.realpath(__file__))
CRYPT_ROOT = '/crypt'

METADATA_FILE = os.path.join(CRYPT_ROOT, 'documents.toml')
USERS_FILE = os.path.join(CRYPT_ROOT, 'users.toml')

app = Flask(__name__)
app.config['SECRET_KEY'] = b'_\xfd\xd9\xe53\x00\x8e\xbc\xa4\x14-\x97\x11\x0e&>'
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

# Filesystem

def shell(script_args):
    return subprocess.run(script_args, capture_output=True).stdout.decode('utf-8')

def cryptfs_create():
    return shell(['/var/lib/etrial/scripts/create-gocryptfs.sh'])

def cryptfs_mount():
    pass

def cryptfs_delete():
    pass

def load_metadata(metadata_file=METADATA_FILE):
    with open(metadata_file) as fd:
        return toml.load(fd)

def save_metadata(metadata, metadata_file=METADATA_FILE):
    with open(metadata_file, 'w') as fd:
        return toml.dump(metadata, fd)

def refresh_hardlinks(metadata, user_group):
    """ For each file in the metadata object, check whether it has been newly
        published or recalled, and add or remove hardlinks in the SFTP chroots
        accordingly. """
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

# Authentication

def get_user():
    fingerprint = urllib.parse.unquote(request.headers.get('X-Ssl-Client-Fingerprint'))
    dn = urllib.parse.unquote(request.headers.get('X-Ssl-Client-Subject'))
    return dn

# Logging

def log_silent(msg, level=logging.INFO):
    if type(msg) != dict: msg = {'message': msg}
    msg['user'] = get_user()
    logging.log(level, json.dumps(msg))
    return msg

def log_flash(msg, level=logging.INFO):
    flash(log_silent(msg, level), {
        logging.INFO: 'info',
        logging.WARNING: 'warning',
        logging.ERROR: 'error',
    }[level])
    return msg

# Pages

@app.route('/')
def redirect_home():
    return render_template('encrypted.html')

@app.route('/documents')
def page_documents():
    # handle sort argments
    sort = { 'field': request.args.get('sort'), 'reverse': request.args.get('reverse') }
    if sort['field'] not in ['added', 'identifier', 'title']:
        if sort['field'] is not None: return redirect('/documents')
        else: sort['field'] = 'added'
    sort['reverse'] = sort['reverse'] == ''
    sort_key = (lambda field: lambda pair: pair[1].get(field) or '')(sort['field'])
    metadata = sorted(load_metadata().items(), key=sort_key, reverse=sort['reverse'])

    user = get_user()
    return render_template('documents.html', metadata=metadata, user=user, sort=sort)

@app.route('/log')
def page_log():
    metadata = load_metadata()
    user = get_user()

    script = [os.path.join(SCRIPT_DIR, 'filtered-journal.sh')]
    stdout = shell(script)
    _json = [json.loads(l) for l in stdout.split('\n') if l != '']

    if not request.args.get('reverse') == '': _json.reverse()

    return render_template('log.html', log=_json)

@app.route('/settings')
def page_settings():
    metadata = load_metadata()
    user = get_user()
    keys = os.listdir(CLIENT_CERT_DIR)
    return render_template('settings.html', keys=keys)

# Document commands

@app.route('/upload', methods=['POST'])
def cmd_documents_upload():
    metadata = load_metadata()
    user = get_user()
    title = request.args.get('filename')
    h = hashlib.blake2b(digest_size=20)
    h.update(request.data)
    _hash = h.hexdigest()
    with open(os.path.join(ADMIN_DIR, 'files', _hash), 'wb') as fd:
        fd.write(request.data)
    metadata[_hash] = {
        'title': title, 'added': datetime.datetime.now(dateutil.tz.tzutc())
    }
    save_metadata(metadata)
    msg = log_flash({
        'message': f'Uploaded {title}.',
        'action': 'upload', 'title': title, 'hash': _hash,
        'size_mb': len(request.data)/10**6
    })
    return msg, 200

@app.route('/publish/<_hash>/<user_group>', methods=['POST'])
def cmd_documents_publish(_hash, user_group):
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
def cmd_documents_recall(_hash, user_group):
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

@app.route('/delete/<_hash>', methods=['POST'])
def cmd_documents_delete(_hash):
    metadata = load_metadata()
    user = get_user()
    published_to = metadata[_hash].get('published')
    if published_to is None or published_to == []:
        msg = log_flash({
            'message': f'Deleting {metadata[_hash].get("title")}.',
            'action': 'delete', 'hash': _hash
        }, logging.WARNING)
        del metadata[_hash]
        save_metadata(metadata)
        return json.dumps(msg), 200
    else:
        msg = log_flash({
            'message': f"Can't delete {metadata[_hash].get('title')}, it's published to {published_to}.",
            'action': 'delete', 'hash': _hash
        }, level=logging.ERROR)
        return json.dumps(msg), 400

# Settings commands

@app.route('/settings/tls/create', methods=['POST'])
def cmd_settings_tls_cert_create():
    pass

@app.route('/settings/ssh/create', methods=['POST'])
def cmd_settings_ssh_key_create():
    pass

@app.route('/settings/cryptfs/create', methods=['POST'])
def cmd_settings_cryptfs_create():
    pass

@app.route('/settings/cryptfs/mount', methods=['POST'])
def cmd_settings_cryptfs_mount():
    pass

@app.route('/settings/cryptfs/delete', methods=['POST'])
def cmd_settings_cryptfs_delete():
    pass

# Template utilities

@app.context_processor
def t_inject_user(): return dict(user=get_user())

@app.context_processor
def t_inject_crypt_root(): return dict(secure_path=CRYPT_ROOT)

def now(): return datetime.datetime.now(dateutil.tz.tzutc())
@app.context_processor
def t_inject_now(): return dict(now=now())

@app.template_filter('parse')
def t_filter_parse(iso8601): return dateutil.parser.parse(iso8601)

@app.template_filter('localise')
def t_filter_localise(dt): return dt.astimezone(dateutil.tz.tzlocal())

@app.template_filter('short_date')
def t_filter_short_date(dt): return dt.strftime('%a %-d %b')

@app.template_filter('long_date')
def t_filter_long_date(dt): return dt.strftime('%a %-d %b %Y')

@app.template_filter('short_time')
def t_filter_short_time(dt): return dt.strftime('%-I:%M %p').lower()

@app.template_filter('long_time')
def t_filter_long_time(dt): return dt.strftime('%-I:%M:%S %p').lower()

@app.template_filter('tz')
def t_filter_tz(dt): return dt.strftime('%Z')
