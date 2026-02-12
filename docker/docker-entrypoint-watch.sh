#!/bin/sh
# Wrapper entrypoint: run original docker entrypoint and watch proxy_rules.conf for reloads

# Trap signals and forward them to nginx
handle_signal() {
  if [ -f /var/run/nginx.pid ]; then
    kill -TERM "$(cat /var/run/nginx.pid)" || true
  fi
}

trap handle_signal TERM INT

# 初始化 SSL 配置（生成空的或有效的 SSL 配置文件）
if [ -x /ssl-renew.sh ]; then
  /ssl-renew.sh init
fi

# Start original entrypoint - pass through CMD args so nginx starts correctly
/docker-entrypoint.sh "$@" &
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

# 启动 SSL 证书自动续期（后台每12小时检查一次）
if [ -x /ssl-renew.sh ] && [ -n "${SSL_DOMAIN:-}" ]; then
  /ssl-renew.sh cron &
  CRON_PID=$!
fi

# Wait for main process and keep container alive
wait $MAIN_PID
exit_code=$?

# Kill watcher and cron if they exist
if [ -n "$WATCH_PID" ]; then
  kill $WATCH_PID 2>/dev/null || true
fi
if [ -n "$CRON_PID" ]; then
  kill $CRON_PID 2>/dev/null || true
fi

exit $exit_code

