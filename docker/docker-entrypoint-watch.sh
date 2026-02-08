#!/bin/sh
# Wrapper entrypoint: run original docker entrypoint and watch proxy_rules.conf for reloads

# Trap signals and forward them to nginx
handle_signal() {
  if [ -f /var/run/nginx.pid ]; then
    kill -TERM "$(cat /var/run/nginx.pid)" || true
  fi
}

trap handle_signal TERM INT

# Start original entrypoint - it will start nginx and stay running
/docker-entrypoint.sh &
MAIN_PID=$!

# Wait for nginx to be ready
sleep 2
retries=0
while [ ! -f /var/run/nginx.pid ] && [ $retries -lt 30 ]; do
  sleep 0.5
  retries=$((retries+1))
done

# Watch config file for changes and reload nginx
if command -v inotifywait >/dev/null 2>&1 && [ -f /etc/nginx/conf.d/proxy_rules.conf ]; then
  inotifywait -m -e close_write /etc/nginx/conf.d/proxy_rules.conf 2>/dev/null | while read -r file action; do
    if [ -f /var/run/nginx.pid ]; then
      nginx -s reload || true
    fi
  done &
  WATCH_PID=$!
fi

# Wait for main process and keep container alive
wait $MAIN_PID
exit_code=$?

# Kill watcher if it exists
if [ -n "$WATCH_PID" ]; then
  kill $WATCH_PID 2>/dev/null || true
fi

exit $exit_code
