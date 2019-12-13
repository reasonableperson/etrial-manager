#!/bin/bash

if [[ $(</proc/sys/kernel/hostname) != "etrial" ]]; then
  echo "You should run this from inside the container."
  exit
fi

if [[ "$1" == "-r" ]]; then $extra_flag="-r"; fi

journalctl $extra_flag -u nginx -u gunicorn -o json \
  --output-fields=UNIT,MESSAGE,SYSLOG_IDENTIFIER | jq -c '

    # These functions attempt to get something useful out of a string, and fail
    # with a null.
    def maybe_nginx: (capture("etrial (?<src>nginx):") | .src) // null;
    def maybe_ip: (capture(" (?<ip>([0-9.]+){3}[0-9]+)[, ]") | .ip) // null;
    def maybe_http_status: (capture("\"(?<qs>[^\"]*)\" (?<code>\\d{3})") | .code) // null;
    def maybe_double_json: (capture("(?<json>\\{.*\\})") | .json | fromjson ) // null;
    def maybe_info: (capture("(?i)(?<info>\\[info].*)") | .info) // null;
    def maybe_warn: (capture("(?i)(?<warn>\\[warn].*)") | .warn) // null;

    # These functions attempt to remove cruft from a string, and fail by passing
    # through the string unmodified.
    def clean_nginx_access: (capture("\"(?<qs>[^\"]*)\" (?<code>\\d{3})") | .qs) // .;

    # These functions delete uninteresting records from the log. They should be
    # used cautiously; you never know when a log might come in handy.
    def filter_static_files: . |
      select(.msg | test("GET /favicon.ico") | not) |
      select(.msg | test("GET /static/ui.js") | not) |
      select(.msg | test("GET /static/style.css") | not) ;
    def filter_logger_debug: . |
      select(.msg | test("loggerdebugger") | not) ;

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
      msg: .MESSAGE,
    } | filter_static_files | filter_logger_debug' 
