FROM nginx:alpine

RUN apk add --no-cache inotify-tools bash netcat-openbsd

COPY docker-entrypoint-watch.sh /docker-entrypoint-watch.sh
RUN chmod +x /docker-entrypoint-watch.sh

ENTRYPOINT ["/docker-entrypoint-watch.sh"]
CMD ["nginx", "-g", "daemon off;"]
