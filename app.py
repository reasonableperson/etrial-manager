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

def refresh_hardlinks(metadata, user_group):
    """ For each file in the metadata object, check whether it has been newly
        published or recalled, and add or remove hardlinks in the SFTP chroots
        accordingly. """
    user_dir = f'/crypt/{user_group}/Documents'
    existing_hardlinks = os.listdir(user_dir)
    for _hash, meta in metadata.items():
        source = os.path.join(CRYPT_ROOT, 'store', _hash)
        destination = os.path.join(user_dir, meta['title'])
        if 'publish' in meta and user_group in meta['publish']:
            if meta['title'] not in existing_hardlinks:
                # These documents have been newly published
                os.link(source, destination)
                log_silent({'action': 'link', 'source': source, 'destination': destination})
        # These documents have been newly recalled
        elif meta['title'] in existing_hardlinks:
            os.remove(destination)
            log_silent({'action': 'unlink', 'destination': destination})

# Authentication

def get_user_cert(username):
    cert_path = f'/crypt/keys/{username}.pfx'
    return cert_path if os.path.exists(cert_path) else None

def get_current_user(full_list=False):
    """ Return the name of the current web interface user, based on their
        SSL fingerprint. This requires access to the user list, which is
        stored in /crypt. This function will throw FileNotFoundError if it is
        called when /crypt is not mounted. """
    fingerprint = urllib.parse.unquote(request.headers.get('X-Ssl-Client-Fingerprint'))
    dn = urllib.parse.unquote(request.headers.get('X-Ssl-Client-Subject'))
    real_name = re.search('CN=([^,]*),', dn).group(1)
    if not os.path.exists(USERS_FILE):
        return {'real_name': real_name}
    else:
        # determine username from realname
        users = load_metadata(metadata_file=USERS_FILE)
        matches = [k for k, v in users.items() if 'name' in v and v['name'] == real_name]
        print(matches)
        # if the current user's real name is already in the USERS_FILE,
        if len(matches) == 1:
            username = matches[0]
            # update their last seen time.
            users[username]['seen'] = now()
        else: # if the user cannot be uniquely matched to the USERS_FILE,
            username = real_name.split(' ')[0].lower()
            # create an entry in the USERS_FILE
            users[username] = {
                'fingerprint': fingerprint,
                'real_name': real_name,
                'seen': now(),
                'added': None,
                'groups': ['admin'],
            } # and save it
            save_metadata(users, metadata_file=USERS_FILE)
        # regardless of whether the current (web) user was extracted from the
        # USERS_FILE or generated for the first time, return the user's metadata.
        # At this point, since we loaded the thing anyway, we might as well
        # return the whole thing if the caller passes full_list=True.
        return users if full_list else users[username]

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
    return render_template('users.html', users=get_current_user(full_list=True), fsdata=fsdata)

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
    metadata[_hash] = dict(title=title, added=now())
    save_metadata(metadata)
    msg = log_flash({
        'message': f'Uploaded {title}.',
        'action': 'upload', 'title': title, 'hash': _hash,
        'size_mb': len(request.data)/10**6
    })
    return msg, 200

@app.route('/documents/grant/<_hash>/<user_group>', methods=['POST'])
def cmd_documents_publish(_hash, user_group):
    metadata = load_metadata()
    doc = metadata[_hash]
    msg = log_flash({
        'message': f'Published {doc["title"]} to {user_group}.',
        'action': 'publish', 'hash': _hash, 'title': doc['title'],
        'user_group': user_group
    })
    if 'publish' not in metadata[_hash]: metadata[_hash]['publish'] = []
    metadata[_hash][user_group] = True
    refresh_hardlinks(metadata, user_group)
    save_metadata(metadata)
    return msg, 200

@app.route('/documents/deny/<_hash>/<user_group>', methods=['POST'])
def cmd_documents_recall(_hash, user_group):
    metadata = load_metadata()
    doc = metadata[_hash]
    msg = log_flash({
        'message': f'Recalled {doc["title"]} from {user_group}.',
        'action': 'recall', 'hash': _hash, 'title': doc['title'],
        'user_group': user_group
    }, logging.WARNING)
    del metadata[_hash][user_group]
    refresh_hardlinks(metadata, user_group)
    save_metadata(metadata)
    return msg, 200

@app.route('/documents/delete/<_hash>', methods=['POST'])
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
        save_metadata(metadata)
        return json.dumps(msg), 200
    else:
        msg = log_flash({
            'message': f"Can't delete {metadata[_hash].get('title')}, it's published to {published_to}.",
            'action': 'delete', 'hash': _hash
        }, level=logging.ERROR)
        return json.dumps(msg), 400

# Users commands

@app.route('/users/add', methods=['POST'])
def cmd_users_add():
    real_name = request.form['name']
    users = get_current_user(full_list=True)
    if real_name is not None and real_name != '':
        username = real_name.split(' ')[0].lower()
        users[username] = {
            'real_name': real_name,
            'seen': now(),
            'added': now(),
        }
        stdout = create_https_client_cert(username, real_name)
        log_flash(stdout)
        users[username]['passphrase'] = stdout[-1]
        users[username]['cert'] = f'{username}.pfx'
        users[username]['key'] = create_ssh_key(username)

        #users[username]['groups'] = ['admin']
        save_metadata(users, metadata_file=USERS_FILE)
    else:
        log_flash(f'That\'s not a valid username.')
    return redirect('/users')

@app.route('/users/delete/<username>/', methods=['POST'])
def cmd_users_delete(username):
    log_flash(f'Deleted user {username}.')
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

def create_ssh_key(username):
    path = f'{username}.ssh.txt'
    stdout = shell([
        'ssh-keygen', '-t', 'rsa', '-m', 'PEM', 
        '-f', os.path.join(CRYPT_ROOT, 'keys', path),
        '-C', f'{username}-{datetime.datetime.now().strftime("%Y-%m-%d")}',
        '-N', ''
    ]).stdout
    log_flash(stdout)
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
