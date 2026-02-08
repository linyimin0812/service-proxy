#!/bin/sh
# Wrapper entrypoint: run original docker entrypoint in background, watch proxy_rules.conf and reload nginx on changes

set -e

# Start original entrypoint in background
/docker-entrypoint.sh &
MAIN_PID=$!

# Wait for nginx master pid to appear
wait_for_nginx() {
  retries=0
  while [ ! -f /var/run/nginx.pid ] && [ $retries -lt 60 ]; do
    sleep 0.5
    retries=$((retries+1))
  done
}

wait_for_nginx

# Watch config file for changes and reload nginx
if command -v inotifywait >/dev/null 2>&1; then
  inotifywait -m -e close_write --format '%w%f' /etc/nginx/conf.d/proxy_rules.conf | while read file; do
    nginx -s reload || true
  done &
fi

wait $MAIN_PID
