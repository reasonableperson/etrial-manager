import base64
import hashlib
import json
import io
import os
import urllib

import toml

from flask import Flask, flash, g, render_template, redirect, request

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'new'
app.config['SECRET_KEY'] = b'_\xfd\xd9\xe53\x00\x8e\xbc\xa4\x14-\x97\x11\x0e&>'

def load_metadata():
    with open('metadata.toml') as fd:
        return toml.load(fd)

def save_metadata(md):
    with open('metadata.toml', 'w') as fd:
        return toml.dump(md, fd)

def get_user_name():
    cert = urllib.parse.unquote(request.headers.get('X-Ssl-Client-Certificate'))
    for c in os.listdir('certs'):
        with open(os.path.join('certs', c)) as fd:
            if cert == fd.read():
                return c.replace('.crt', '')

@app.route('/')
def home():
    metadata = load_metadata()
    user = get_user_name()
    cert = urllib.parse.unquote(request.headers.get('X-Ssl-Client-Certificate'))
    return render_template('home.html', files=metadata, user=user)

@app.route('/admin')
def admin():
    metadata = load_metadata()
    user = get_user_name()
    certs = os.listdir('certs')
    return render_template('admin.html', certs=certs)

@app.route('/log')
def log():
    metadata = load_metadata()
    user = get_user_name()
    return render_template('log.html')

# Assign the next available MFI or exhibit number.
@app.route('/identify/<_hash>/<prefix>', methods=['POST'])
def identify(_hash, prefix):
    metadata = load_metadata()
    user = get_user_name()
    print(_hash, prefix)
    existing_identifiers = [d.replace(prefix, '') for d in metadata.values() if d.get('id') is not None and d.get('id')[:len(prefix)] == prefix]
    print('existing ids:', existing_identifiers)
    metadata[_hash].update({ 'identifier': f'{prefix} 1' })
    save_metadata(metadata)
    return 'ok'

# Assign the next available MFI or exhibit number.
@app.route('/delete/<_hash>', methods=['POST'])
def delete(_hash):
    metadata = load_metadata()
    user = get_user_name()
    del metadata[_hash]
    save_metadata(metadata)
    return 'ok'

@app.route('/upload', methods=['POST'])
def upload():
    metadata = load_metadata()
    user = get_user_name()
    print(f'Received {len(request.data)} bytes.')
    title = request.args.get('filename')
    h = hashlib.blake2b(digest_size=20)
    h.update(request.data)
    _hash = h.hexdigest()
    with open(f'/secure/docs/{_hash}', 'wb') as fd:
        fd.write(request.data)
        print(f'/secure/docs/{_hash}')
    metadata[_hash] = { 'title': title }
    save_metadata(metadata)
    return 'Thanks.'
