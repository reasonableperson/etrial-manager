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

@app.route('/')
def home():
    metadata = load_metadata()
    cert = urllib.parse.unquote(request.headers.get('X-Ssl-Client-Certificate'))
    return render_template('home.html', files=metadata, cert=cert)

@app.route('/admin')
def admin():
    metadata = load_metadata()
    return render_template('admin.html')

@app.route('/log')
def log():
    metadata = load_metadata()
    return render_template('log.html')

@app.route('/upload', methods=['POST'])
def upload():
    metadata = load_metadata()
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
