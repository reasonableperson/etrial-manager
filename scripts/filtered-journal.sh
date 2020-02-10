#!/bin/bash

if [[ $(</proc/sys/kernel/hostname) != "etrial" ]]; then
  echo "You should run this from inside the container."
  exit
fi

if [[ "$1" == "-r" ]]; then $extra_flag="-r"; fi

journalctl $extra_flag -u nginx -u etrial-manager -o json \
  -n 500 --output-fields=UNIT,MESSAGE,SYSLOG_IDENTIFIER | jq -c '

    # These functions attempt to get something useful out of a string, and fail
    # with a null.
    def maybe_nginx: (capture("etrial (?<src>nginx):") | .src) // null;
    def maybe_ip: (capture(" (?<ip>([0-9.]{2,}){3}[0-9]+)[, ]") | .ip) // null;
    def maybe_http_status: (capture("\"(?<qs>[^\"]*)\" (?<code>\\d{3})") | .code) // null;
    def maybe_double_json: (capture("(?<json>\\{.*\\})") | .json | fromjson ) // null;
    def maybe_info: (capture("(?i)(?<info>\\[info].*)") | .info) // null;
    def maybe_warn: (capture("(?i)(?<warn>\\[warn].*)") | .warn) // null;

    # These functions attempt to remove cruft from a string, and fail by passing
    # through the string unmodified.
    def clean_nginx_access: (capture("\"(?<qs>[^\"]*) HTTP/1\\.1\" (?<code>\\d{3})") | .qs) // .;

    # These functions delete uninteresting records from the log. They should be
    # used cautiously; you never know when a log might come in handy.
    def filter_static_files: . |
      select(.msg | test("GET /favicon.ico") | not) |
      select(.msg | test("GET /static/ui.js") | not) |
      select(.msg | test("GET /static/style.css") | not) |
      select(.msg | test("buffered to a temporary file") | not) |
      select(.msg | test("closed keepalive connection") | not) |
      select(.msg | test("client closed connection while waiting for request") | not) |
      select(.msg | test("127.0.0.1 - -") | not) |
      select(.msg | test("GET /static/style.css") | not) |
      select(.msg | test("__debugger__") | not) |
      select(.msg | test("INFO:werkzeug") | not) |
      select(.msg | test("GET /static/style.css") | not) ;

    # https://github.com/benoitc/gunicorn/issues/2091
    def filter_gunicorn_bug_aug19: . |
      select(.msg | test("RuntimeWarning: line buffering") | not) |
      select(.msg | test("return io.open.fd, .args, ..kwargs.") | not) ;

    def filter_gunicorn: . |
      select(.msg | test(".INFO. Booting worker") | not) |
      select(.msg | test(".INFO. Worker exiting") | not) ;

    # This filter consumes the journalctl output and produces a nicely-
    # formatted subset of it for rendering as HTML.
    { 
      timestamp: (.__REALTIME_TIMESTAMP | tonumber | ./1e6 | todate),
      app: (.SYSLOG_IDENTIFIER // (.MESSAGE | maybe_nginx )),
      ip: (.MESSAGE | maybe_ip),
      http_status: (.MESSAGE | maybe_http_status),
      extra: (.MESSAGE | maybe_double_json),
      info: (.MESSAGE | maybe_info),
      warn: (.MESSAGE | maybe_warn),
      msg: (.MESSAGE | clean_nginx_access),
    } | filter_static_files | filter_gunicorn | filter_gunicorn_bug_aug19' 
