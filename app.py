import collections
import datetime
import hashlib
import json
import logging
import os
import re
import subprocess
import time
import urllib

import dateutil.parser
import dateutil.tz
import toml
from flask import Flask, flash, g, render_template, redirect, request

# Configuration

VERSION = "0.2.0"

CODE_ROOT = os.path.dirname(os.path.realpath(__file__))
DATA_ROOT = '/home/etrial'
WEBDAV_ROOT = os.path.join(DATA_ROOT, 'dav')

METADATA_FILE = os.path.join(DATA_ROOT, 'documents.toml.txt')
USERS_FILE = os.path.join(DATA_ROOT, 'users.toml.txt')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

# Filesystem

def shell(script_args, input=None, check=True):
    try:
        return subprocess.check_output(script_args).decode('utf-8')
    except subprocess.CalledProcessError as e:
        log_silent(e.output.decode('utf-8'))
        raise

def load_metadata(metadata_file=METADATA_FILE):
    if not os.path.exists(metadata_file):
        return {}
    with open(metadata_file) as fd:
        return toml.load(fd)

def save_metadata(metadata, metadata_file=METADATA_FILE):
    with open(metadata_file, 'w') as fd:
        return toml.dump(metadata, fd)

def refresh_hardlinks(documents, user_group):
    """ For each document in the documents file, check whether it has been newly
        published or recalled, and add or remove hardlinks in the WebDAV dir
        accordingly. """
    user_dir = os.path.join(WEBDAV_ROOT, user_group)
    log_silent(f'Refreshing hardlinks in {user_dir}.')
    existing_hardlinks = os.listdir(user_dir) # names only, no path
    for _hash, document in documents.items():
        source = os.path.join(DATA_ROOT, 'store', _hash)
        destination = os.path.join(user_dir, document['title'])
        # If the document is supposed to be published but there's no existing
        # hardlink, create one.
        if user_group in document['groups']:
            if not os.path.exists(destination):
                os.link(source, destination)
                log_silent({'action': 'link', 'source': source, 'destination': destination})
            else: existing_hardlinks.remove(document['title'])
        # If there is a hardlink but the document isn't supposed to be published,
        # remove the hardlink.
        elif os.path.exists(destination):
            os.remove(destination)
            existing_hardlinks.remove(document['title'])
            log_silent({'action': 'unlink', 'destination': destination})
    # If there is a hardlink that didn't get accounted for by the previous two
    # cases (and thus removed from existing_hardlinks), remove it now, because
    # the document itself was deleted.
    for link in existing_hardlinks:
        destination = os.path.join(user_dir, link) 
        os.remove(destination)
        log_silent({'action': 'unlink', 'destination': destination})

def refresh_authorized_keys(users, dav_group):
    """ Find the set of users who are authorised to access a particular Unix
        account, and write a suitable authorized_keys file for the account. """
    authorized_users = [k for k, v in users.items() if dav_group in v['groups'] and 'key' in v]
    authorized_keys_file = os.path.join(DATA_ROOT, 'keys', f'{dav_group}.authorized')
    os.remove(authorized_keys_file)
    log_silent(f"Clearing {authorized_keys_file}.")
    with open(authorized_keys_file, 'w') as fd:
        for u in authorized_users:
            pubkey = open(os.path.join(DATA_ROOT, 'keys', f'{u}.ssh.pub')).read()
            log_silent(f"Writing {u}.ssh.pub to {authorized_keys_file}.")
            fd.write(pubkey)

# Authentication

def get_user_cert(username):
    cert_path = os.path.join(DATA_ROOT, 'keys', f'{username}.pfx')
    return cert_path if os.path.exists(cert_path) else None

def get_current_user():
    """ Return the metadata for the current web interface user, based on their
        SSL fingerprint, and update their last seen time. """
    fingerprint = urllib.parse.unquote(request.headers.get('X-Ssl-Client-Fingerprint'))
    dn = urllib.parse.unquote(request.headers.get('X-Ssl-Client-Subject'))
    real_name = re.search('CN=([^,]*),', dn).group(1)
    # If /crypt is not mounted, just trust the real name provided in the
    # HTTPS client certificate.
    if not os.path.exists(USERS_FILE):
        return {'real_name': real_name}
    # Otherwise, load the users file, and look for the current user.
    users = load_metadata(metadata_file=USERS_FILE)
    matches = [k for k, v in users.items() if 'real_name' in v and v['real_name'] == real_name]
    username = matches[0] if len(matches) == 1 else None
    # If they're not in there, this is probably an initial login -- bootstrap
    # the user file with this new user.
    if not username:
        username = real_name.split(' ')[0].lower()
        users[username] = {
            'fingerprint': fingerprint,
            'real_name': real_name,
            'seen': now(),
            'added': None,
            'groups': ['admin'],
        }
        save_metadata(users, metadata_file=USERS_FILE)
    else: # Otherwise, this is a known user. Update their last seen time.
        users[username]['seen'] = now()
    # Save changes to the users file and return.
    save_metadata(users, metadata_file=USERS_FILE)
    return users[username]

# Logging

def log_silent(msg, level=logging.INFO):
    if type(msg) != dict: msg = {'message': msg}
    # generally we want to log the user performing the action, but we may also
    # perform some loggable actions (eg. decryption) while /crypt is
    # unavailable, so we can ignore it when get_current_user() fails
    msg['user'] = get_current_user()['real_name']
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
def page_home():
    return redirect('/documents')

@app.route('/documents')
def page_documents():
    # handle any sort field specified by the user
    sort = { 'field': request.args.get('sort'), 'reverse': request.args.get('reverse') }
    if sort['field'] not in ['added', 'identifier', 'title']:
        if sort['field'] is not None: return redirect('/documents')
        else: sort['field'] = 'added'
    sort['reverse'] = sort['reverse'] == ''
    sort_key = (lambda field: lambda pair: pair[1].get(field) or '')(sort['field'])

    # load toml file and sort it accordingly
    metadata = sorted(load_metadata().items(), key=sort_key, reverse=sort['reverse'])

    user = get_current_user()
    return render_template('documents.html', documents=metadata, user=user, sort=sort)

@app.route('/log')
def page_log():
    metadata = load_metadata()
    user = get_current_user()

    script = [os.path.join(CODE_ROOT, 'scripts', 'filtered-journal.sh')]
    stdout = shell(script)
    _json = [json.loads(l) for l in stdout.split('\n') if l != '']

    if not request.args.get('reverse') == '': _json.reverse()

    return render_template('log.html', metadata=metadata, log=_json)

@app.route('/users')
def page_users():
    df = shell(['df', '-B', '1', '/']).split('\n')[1].split()
    domain = shell(['grep', '-oP', r'server_name +\K([^;]*)', '/etc/nginx/sites-enabled/default']).strip()
    with open(os.path.join(DATA_ROOT, 'dav.htpasswd.clear')) as fd:
        dav_users = [s.split(':') for s in fd.read().split()]
    crypt_used = int(shell(['du', '-b', '-s', DATA_ROOT], check=False).split()[0])
    fsdata = dict(total=int(df[1]), used=int(df[2]), crypt_used=crypt_used)
    return render_template('users.html', users=load_metadata(metadata_file=USERS_FILE), fsdata=fsdata, dav_users=dav_users, domain=domain)

# Document commands

@app.route('/documents/add', methods=['POST'])
def cmd_documents_upload():
    metadata = load_metadata()
    user = get_current_user()
    title = request.args.get('filename')
    h = hashlib.blake2b(digest_size=20)
    h.update(request.data)
    _hash = h.hexdigest()
    with open(os.path.join(DATA_ROOT, 'store', _hash), 'wb') as fd:
        fd.write(request.data)
    metadata[_hash] = dict(title=title, added=now(), groups=[])
    save_metadata(metadata)
    msg = log_flash({
        'message': f'Uploaded {title}.',
        'action': 'upload', 'title': title, 'hash': _hash,
        'size_mb': len(request.data)/10**6
    })
    return json.dumps(msg), 200

@app.route('/documents/grant/<_hash>/<user_group>', methods=['POST'])
def cmd_documents_publish(_hash, user_group):
    assert user_group in ['judge', 'jury', 'witness']
    metadata = load_metadata()
    doc = metadata[_hash]
    msg = log_flash({
        'message': f'Published {doc["title"]} to {user_group}.',
        'action': 'publish', 'hash': _hash, 'title': doc['title'],
        'user_group': user_group
    })
    if user_group not in metadata[_hash]['groups']:
        metadata[_hash]['groups'].append(user_group)
    refresh_hardlinks(metadata, user_group)
    save_metadata(metadata)
    return json.dumps(msg), 200

@app.route('/documents/deny/<_hash>/<user_group>', methods=['POST'])
def cmd_documents_recall(_hash, user_group):
    assert user_group in ['judge', 'jury', 'witness']
    metadata = load_metadata()
    doc = metadata[_hash]
    msg = log_flash({
        'message': f'Recalled <b>{doc["title"]}</b> from <b>{user_group}</b>.',
        'action': 'recall', 'hash': _hash, 'title': doc['title'],
        'user_group': user_group
    }, logging.WARNING)
    if user_group in doc['groups']: doc['groups'].remove(user_group)
    refresh_hardlinks(metadata, user_group)
    save_metadata(metadata)
    return json.dumps(msg), 200

@app.route('/documents/edit/<_hash>/title', methods=['POST'])
def cmd_documents_edit_title(_hash):
    pass

@app.route('/documents/edit/<_hash>/title', methods=['POST'])
def cmd_documents_edit_description(_hash):
    pass

@app.route('/documents/delete/<_hash>/', methods=['POST'])
def cmd_documents_delete(_hash):
    metadata = load_metadata()
    user = get_current_user()
    published_to = metadata[_hash].get('publish')
    if published_to is None or published_to == []:
        msg = log_flash({
            'message': f'Deleted {metadata[_hash].get("title")}.',
            'action': 'delete', 'hash': _hash
        }, logging.WARNING)
        del metadata[_hash]
        for user_group in ['judge', 'jury', 'witness']:
            refresh_hardlinks(metadata, user_group)
        save_metadata(metadata)
        return json.dumps(msg), 200
    else:
        msg = log_flash({
            'message': f"Can't delete {metadata[_hash].get('title')}, it's published to {published_to}.",
            'action': 'delete', 'hash': _hash
        }, level=logging.ERROR)
        return json.dumps(msg), 400

# Users commands

def create_user(real_name, generate_https=True):
    username = real_name.split(' ')[0].lower()
    user = {
        'real_name': real_name,
        'seen': now(),
        'added': now(),
    }
    if generate_https:
        stdout = create_https_client_cert(username, real_name)
        log_silent(stdout)
        user['passphrase'] = stdout[-1]
        user['cert'] = f'{username}.pfx'
        user['groups'] = ['admin']
    return username, user

@app.route('/users/add', methods=['POST'])
def cmd_users_add():
    real_name = request.form['name']
    users = load_metadata(metadata_file=USERS_FILE)
    if real_name is not None and real_name != '':
        try:
            username, user = create_user(real_name)
            users[username] = user
            save_metadata(users, metadata_file=USERS_FILE)
            log_flash(f'Created new user {username}.')
        except:
            log_flash(f'User creation error.', logging.ERROR)
    else:
        log_flash(f'That\'s not a valid username.')
    return redirect('/users')

@app.route('/users/grant/<username>/<dav_group>', methods=['POST'])
def cmd_users_grant(username, dav_group):
    assert dav_group in ['judge', 'jury', 'witness']
    users = load_metadata(metadata_file=USERS_FILE)
    if dav_group not in users[username]['groups']:
        users[username]['groups'].append(dav_group)
    save_metadata(users, metadata_file=USERS_FILE)
    refresh_authorized_keys(users, dav_group)
    msg = log_flash({
        'message': f'Granted user {username} access to {dav_group}.',
        'action': 'user_grant', 'username': username, 'dav_group': dav_group
    })
    return json.dumps(msg), 200

@app.route('/users/deny/<username>/<dav_group>', methods=['POST'])
def cmd_users_deny(username, dav_group):
    assert dav_group in ['judge', 'jury', 'witness']
    users = load_metadata(metadata_file=USERS_FILE)
    if dav_group in users[username]['groups']:
        users[username]['groups'].remove(dav_group)
    save_metadata(users, metadata_file=USERS_FILE)
    refresh_authorized_keys(users, dav_group)
    msg = log_flash({
        'message': f'Revoked user {username}\'s access to {dav_group}.',
        'action': 'user_grant', 'username': username, 'dav_group': dav_group
        })
    return json.dumps(msg), 200

@app.route('/users/delete/<username>/', methods=['POST'])
def cmd_users_delete(username):
    users = load_metadata(metadata_file=USERS_FILE)
    for dav_group in users[username]['groups']:
        refresh_authorized_keys(users, sftp_group)
    del users[username]
    path = os.path.join(DATA_ROOT, 'keys', f'{username}.pfx')
    if os.path.exists(path):
        os.remove(path)
    save_metadata(users, metadata_file=USERS_FILE)
    msg = log_flash({
        'message': f'Deleted user {username}.',
        'action': 'user_delete', 'username': username,
    })
    return redirect('/users')

def create_https_client_cert(username, real_name):
    script_result = shell([
        os.path.join(CODE_ROOT, 'scripts', 'add-https-user.sh'),
        username, real_name,
        os.path.join(DATA_ROOT, 'keys')
    ], check=False)
    # if we don't check the shell() call, we can log stderr before raising
    # an exception if there was a failure
    log_silent(['stdout', script_result])
    assert script_result.returncode == 0

    # the last line of the script's output contains the user's passphrase;
    # we'll use the existence of this passphrase to decide whether the user
    # is an admin or not
    return script_result.stdout.split('\n')

# Template utilities

def now(): return datetime.datetime.now(dateutil.tz.tzutc())
@app.context_processor
def t_inject_user(): return {
    'user': get_current_user(),
    'now': now(),
    'version': VERSION,
}

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
