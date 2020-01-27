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

CODE_ROOT = os.path.dirname(os.path.realpath(__file__))
CRYPT_ROOT = '/crypt'

METADATA_FILE = os.path.join(CRYPT_ROOT, 'documents.toml.txt')
USERS_FILE = os.path.join(CRYPT_ROOT, 'users.toml.txt')

app = Flask(__name__)
app.config['SECRET_KEY'] = b'_\xfd\xd9\xe53\x00\x8e\xbc\xa4\x14-\x97\x11\x0e&>'
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

# Filesystem

def shell(script_args, input=None, check=True):
    try:
        return subprocess.run(script_args, capture_output=True,
            check=check, input=input, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        log_silent(e.output)
        raise

def load_metadata(metadata_file=METADATA_FILE):
    with open(metadata_file) as fd:
        return toml.load(fd)

def save_metadata(metadata, metadata_file=METADATA_FILE):
    with open(metadata_file, 'w') as fd:
        return toml.dump(metadata, fd)

def refresh_hardlinks(documents, user_group):
    """ For each document in the documents file, check whether it has been newly
        published or recalled, and add or remove hardlinks in the SFTP chroots
        accordingly. """
    user_dir = f'/crypt/{user_group}/Documents'
    log_silent(f'Refreshing hardlinks in /crypt/{user_group}/Documents.')
    existing_hardlinks = os.listdir(user_dir) # names only, no path
    for _hash, document in documents.items():
        source = os.path.join(CRYPT_ROOT, 'store', _hash)
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


def refresh_authorized_keys(users, sftp_group):
    """ Find the set of users who are authorised to access a particular Unix
        account, and write a suitable authorized_keys file for the account. """
    authorized_users = [k for k, v in users.items() if sftp_group in v['groups'] and 'key' in v]
    authorized_keys_file = os.path.join(CRYPT_ROOT, 'keys', f'{sftp_group}.authorized')
    os.remove(authorized_keys_file)
    log_silent(f"Clearing {authorized_keys_file}.")
    with open(authorized_keys_file, 'w') as fd:
        for u in authorized_users:
            pubkey = open(os.path.join(CRYPT_ROOT, 'keys', f'{u}.ssh.pub')).read()
            log_silent(f"Writing {u}.ssh.pub to {authorized_keys_file}.")
            fd.write(pubkey)

# Authentication

def get_user_cert(username):
    cert_path = f'/crypt/keys/{username}.pfx'
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
    if not os.path.exists(METADATA_FILE): return redirect('/encrypted')
    return redirect('/documents')

def purge_cryptfs():
    """ Unmounts /crypt and deletes ~etrial/crypt, permanently deleting all
        user data. """
    log_silent('Creating new encrypted volume.')
    stdout = shell([
        os.path.join(CODE_ROOT, 'scripts', 'create-gocryptfs.sh'), 'purge'
    ]).stdout
    key = stdout.split('\n')[0]
    return render_template('encrypted.html', key=key)

@app.route('/encrypted')
def page_encrypted():
    if os.path.exists(METADATA_FILE): return redirect('/')
    if os.path.exists('/home/etrial/crypt'):
        return render_template('encrypted.html')
    else:
        return purge_cryptfs()

@app.route('/decrypt', methods=['POST'])
def cmd_decrypt():
    # if the metadata file already exists, you shouldn't be here
    if (os.path.exists(METADATA_FILE)):
        return redirect('/')
    # if a key has been provided, try to decrypt with it
    elif 'key' in request.form:
        with open('/tmp/crypt.key', 'w') as fd:
            fd.write(request.form['key'] + '\n')
        time.sleep(0.5)
        if os.path.exists(METADATA_FILE):
            log_silent('Decrypted filesystem.')
            return redirect('/documents')
        else:
            log_flash('Failed to decrypt filesystem.', logging.ERROR)
            return redirect('/encrypted')
    elif 'action' in request.form:
        if request.form['action'] == 'delete all my data':
            return purge_cryptfs()
        else:
            log_flash('You didn\'t seem sure enough. Nothing was done.', logging.ERROR)
            return redirect('/encrypted')

@app.route('/lock')
def cmd_lock():
    stdout = shell(['touch', '/tmp/crypt.lock']).stdout
    log_flash('Server locked.')
    time.sleep(0.5)
    # this should, in turn, resolve to /encrypted, but if it doesn't, the user
    # may at least realise that something is wrong
    return redirect('/')

@app.route('/documents')
def page_documents():
    if not os.path.exists(METADATA_FILE): return redirect('/encrypted')
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
    if not os.path.exists(METADATA_FILE): return redirect('/encrypted')
    metadata = load_metadata()
    user = get_current_user()

    script = [os.path.join(CODE_ROOT, 'scripts', 'filtered-journal.sh')]
    stdout = shell(script).stdout
    _json = [json.loads(l) for l in stdout.split('\n') if l != '']

    if not request.args.get('reverse') == '': _json.reverse()

    return render_template('log.html', metadata=metadata, log=_json)

@app.route('/users')
def page_users():
    if not os.path.exists(METADATA_FILE): return redirect('/encrypted')
    df = shell(['df', '-B', '1', '/']).stdout.split('\n')[1].split()
    crypt_used = int(shell(['du', '-b', '-s', '/crypt'], check=False).stdout.split()[0])
    fsdata = dict(total=int(df[1]), used=int(df[2]), crypt_used=crypt_used)
    return render_template('users.html', users=load_metadata(metadata_file=USERS_FILE), fsdata=fsdata)

# Document commands

@app.route('/documents/add', methods=['POST'])
def cmd_documents_upload():
    if not os.path.exists(METADATA_FILE): return redirect('/encrypted')
    metadata = load_metadata()
    user = get_current_user()
    title = request.args.get('filename')
    h = hashlib.blake2b(digest_size=20)
    h.update(request.data)
    _hash = h.hexdigest()
    with open(os.path.join(CRYPT_ROOT, 'store', _hash), 'wb') as fd:
        fd.write(request.data)
    metadata[_hash] = dict(title=title, added=now(), groups=[])
    save_metadata(metadata)
    msg = log_flash({
        'message': f'Uploaded {title}.',
        'action': 'upload', 'title': title, 'hash': _hash,
        'size_mb': len(request.data)/10**6
    })
    return msg, 200

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
    return msg, 200

@app.route('/documents/deny/<_hash>/<user_group>', methods=['POST'])
def cmd_documents_recall(_hash, user_group):
    assert user_group in ['judge', 'jury', 'witness']
    metadata = load_metadata()
    doc = metadata[_hash]
    msg = log_flash({
        'message': f'Recalled {doc["title"]} from {user_group}.',
        'action': 'recall', 'hash': _hash, 'title': doc['title'],
        'user_group': user_group
    }, logging.WARNING)
    if user_group in doc['groups']: doc['groups'].remove(user_group)
    refresh_hardlinks(metadata, user_group)
    save_metadata(metadata)
    return msg, 200

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

def create_user(real_name, generate_https=True, generate_ssh=True):
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
    if generate_ssh:
        user['key'] = create_ssh_key(username)
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

@app.route('/users/grant/<username>/<sftp_group>', methods=['POST'])
def cmd_users_grant(username, sftp_group):
    assert sftp_group in ['judge', 'jury', 'witness']
    users = load_metadata(metadata_file=USERS_FILE)
    if sftp_group not in users[username]['groups']:
        users[username]['groups'].append(sftp_group)
    save_metadata(users, metadata_file=USERS_FILE)
    refresh_authorized_keys(users, sftp_group)
    msg = log_flash({
        'message': f'Granted user {username} access to {sftp_group}.',
        'action': 'user_grant', 'username': username, 'sftp_group': sftp_group
    })
    return msg, 200

@app.route('/users/deny/<username>/<sftp_group>', methods=['POST'])
def cmd_users_deny(username, sftp_group):
    assert sftp_group in ['judge', 'jury', 'witness']
    users = load_metadata(metadata_file=USERS_FILE)
    if sftp_group in users[username]['groups']:
        users[username]['groups'].remove(sftp_group)
    save_metadata(users, metadata_file=USERS_FILE)
    refresh_authorized_keys(users, sftp_group)
    msg = log_flash({
        'message': f'Revoked user {username}\'s access to {sftp_group}.',
        'action': 'user_grant', 'username': username, 'sftp_group': sftp_group
    })
    return msg, 200

@app.route('/users/delete/<username>/', methods=['POST'])
def cmd_users_delete(username):
    users = load_metadata(metadata_file=USERS_FILE)
    for sftp_group in users[username]['groups']:
        refresh_authorized_keys(users, sftp_group)
    del users[username]
    for ext in ['pfx', 'ssh', 'ssh.pub']:
        path = os.path.join(CRYPT_ROOT, 'keys', f'{username}.{ext}')
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
        os.path.join(CRYPT_ROOT, 'keys', 'client.crt'),
        os.path.join(CRYPT_ROOT, 'keys', 'client.key'),
        os.path.join(CRYPT_ROOT, 'keys')
    ], check=False)
    # if we don't check the shell() call, we can log stderr before raising
    # an exception if there was a failure
    log_silent(['stdout', script_result.stdout])
    log_silent(['stderr', script_result.stderr])
    assert script_result.returncode == 0

    # the last line of the script's output contains the user's passphrase;
    # we'll use the existence of this passphrase to decide whether the user
    # is an admin or not
    return script_result.stdout.split('\n')

# Shell out to ssh-keygen to generate an ssh key for a new user, and return the
# relative path to the key.
def create_ssh_key(username):
    path = f'{username}.ssh'
    full_path = os.path.join(CRYPT_ROOT, 'keys', path)
    stdout = shell([
        'ssh-keygen', '-t', 'rsa', '-m', 'PEM', 
        '-f', full_path,
        '-C', f'{username}-{datetime.datetime.now().strftime("%Y-%m-%d")}',
        '-N', ''
    ]).stdout
    log_silent(stdout)
    # You're not supposed to do this with SSH keys, but in this case, we want
    # to serve it over HTTP (to authorised administrators).
    stdout = shell(['chmod', 'o+r', full_path])
    return path

# Template utilities

@app.context_processor
def t_inject_user(): return dict(user=get_current_user())

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
