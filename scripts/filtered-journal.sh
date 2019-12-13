#!/bin/bash

if [[ $(</proc/sys/kernel/hostname) != "etrial" ]]; then
  echo "You should run this from inside the container."
  exit
fi

journalctl -f -u nginx -u gunicorn -o json \
  --output-fields=UNIT,MESSAGE,SYSLOG_IDENTIFIER | jq -c '

    # These functions attempt to get something useful out of a string, and fail
    # with a null.
    def maybe_nginx: (capture("(?<src>nginx)") | .src) // null;
    def maybe_ip: (capture(" (?<ip>([0-9.]+){3}[0-9]+)[, ]") | .ip) // null;
    def maybe_http_status: (capture("\" (?<code>[0-9]{3}) ") | .code) // null;

    # These functions attempt to remove cruft from a string, and fail by passing
    # through the string unmodified.
    def clean_nginx_access: (capture("\"(?<qs>[^\"]*)\"") | .qs) // .;
    def clean_info: (capture("(?i)(?<info>\\[info].*)") | .info) // .;

    # These functions delete uninteresting records from the log. They should be
    # used cautiously; you never know when a log might come in handy.
    def filter_static_files: . |
      select(test("GET /favicon.ico") | not) |
      select(test("GET /static/ui.js") | not) |
      select(test("GET /static/style.css") | not) ;

    # This filter consumes the journalctl output and produces a nicely-
    # formatted subset of it for rendering as HTML.
    { 
      timestamp: (.__REALTIME_TIMESTAMP | tonumber | ./1e6 | todate),
      source: (.SYSLOG_IDENTIFIER // (.MESSAGE | maybe_nginx )),
      ip: .MESSAGE | maybe_ip,
      http_status: .MESSAGE | maybe_http_status,
      msg_clean: .MESSAGE | clean_nginx_access | clean_info | filter_static_files,
      msg_original: .MESSAGE,
    }' 
