FROM nginx:alpine

RUN apk add --no-cache inotify-tools bash netcat-openbsd certbot certbot-nginx

# 创建 ACME 验证目录和证书目录
RUN mkdir -p /var/www/certbot /etc/letsencrypt /var/lib/letsencrypt

COPY docker-entrypoint-watch.sh /docker-entrypoint-watch.sh
COPY ssl-renew.sh /ssl-renew.sh
RUN chmod +x /docker-entrypoint-watch.sh /ssl-renew.sh

ENTRYPOINT ["/docker-entrypoint-watch.sh"]
CMD ["nginx", "-g", "daemon off;"]

