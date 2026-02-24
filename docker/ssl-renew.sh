#!/bin/bash
# SSL 证书自动签发与续期脚本
# 用法:
#   首次签发: /ssl-renew.sh issue
#   续期:     /ssl-renew.sh renew
#   定时续期: /ssl-renew.sh cron (后台运行，每12小时检查一次)

set -e

SSL_DOMAIN="${SSL_DOMAIN:-}"
SSL_EMAIL="${SSL_EMAIL:-}"
WEBROOT_PATH="/var/www/certbot"
SSL_CONF_DIR="/etc/nginx/conf.d"
SSL_REDIRECT_CONF="${SSL_CONF_DIR}/ssl_redirect.conf"
SSL_SERVER_CONF="${SSL_CONF_DIR}/ssl_server.conf"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SSL] $1"
}

# 解析逗号分隔的域名列表，返回第一个域名（主域名）
get_primary_domain() {
    echo "${SSL_DOMAIN}" | tr ',' '\n' | head -1 | tr -d ' '
}

# 将逗号分隔的域名列表转为空格分隔（用于 server_name）
get_all_domains_space() {
    echo "${SSL_DOMAIN}" | tr ',' ' ' | sed 's/  */ /g'
}

# 将逗号分隔的域名列表转为 certbot -d 参数
get_certbot_domain_args() {
    local args=""
    local domain
    for domain in $(echo "${SSL_DOMAIN}" | tr ',' ' '); do
        domain=$(echo "$domain" | sed 's/^ *//;s/ *$//')
        [ -n "$domain" ] && args="${args} -d ${domain}"
    done
    echo "$args"
}

generate_ssl_nginx_config() {
    local primary_domain
    primary_domain=$(get_primary_domain)
    local all_domains
    all_domains=$(get_all_domains_space)
    local cert_path="/etc/letsencrypt/live/${primary_domain}"

    if [ ! -f "${cert_path}/fullchain.pem" ]; then
        log "证书文件不存在: ${cert_path}/fullchain.pem，跳过 SSL 配置生成"
        return 1
    fi

    log "生成 SSL Nginx 配置（域名: ${all_domains}）..."

    # 生成 HTTP -> HTTPS 重定向配置（使用 if 指令避免与已有 location / 冲突）
    cat > "${SSL_REDIRECT_CONF}" <<EOF
# 自动生成 - HTTP 重定向到 HTTPS（ACME 验证路径除外）
# 使用 set + if 方式，避免与 server 块中已有的 location / 冲突
set \$redirect_to_https 1;

# ACME 验证路径不重定向
if (\$uri ~* ^/.well-known/acme-challenge/) {
    set \$redirect_to_https 0;
}

if (\$redirect_to_https = 1) {
    return 301 https://\$host\$request_uri;
}
EOF

    # 生成 HTTPS server 配置
    cat > "${SSL_SERVER_CONF}" <<EOF
# 自动生成 - HTTPS 服务器配置
# 支持域名: ${all_domains}
server {
    listen 443 ssl http2;
    server_name ${all_domains};

    # SSL 证书
    ssl_certificate ${cert_path}/fullchain.pem;
    ssl_certificate_key ${cert_path}/privkey.pem;

    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 管理系统 API
    location ~ ^/api/(rules|reload|health|config) {
        proxy_pass http://fastapi_backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }

    # 健康检查端点
    location /health {
        proxy_pass http://fastapi_backend/health;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        access_log off;
    }

    # 动态代理规则
    include /etc/nginx/conf.d/proxy_rules.conf;

    # 管理页面（兜底）
    location / {
        proxy_pass http://fastapi_backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
}
EOF

    log "SSL Nginx 配置已生成"
    return 0
}

clear_ssl_nginx_config() {
    # 清空 SSL 配置文件（保留空文件，避免 nginx include 报错）
    echo "# SSL 未启用" > "${SSL_REDIRECT_CONF}"
    echo "# SSL 未启用" > "${SSL_SERVER_CONF}"
}

issue_certificate() {
    if [ -z "${SSL_DOMAIN}" ]; then
        log "错误: 未设置 SSL_DOMAIN 环境变量，无法签发证书"
        exit 1
    fi

    if [ -z "${SSL_EMAIL}" ]; then
        log "错误: 未设置 SSL_EMAIL 环境变量，无法签发证书"
        exit 1
    fi

    local domain_args
    domain_args=$(get_certbot_domain_args)
    log "开始为域名 ${SSL_DOMAIN} 签发 SSL 证书..."
    log "certbot 参数:${domain_args}"

    eval certbot certonly \
        --webroot \
        --webroot-path=\"${WEBROOT_PATH}\" \
        --email \"${SSL_EMAIL}\" \
        --agree-tos \
        --no-eff-email \
        --force-renewal \
        ${domain_args}

    if [ $? -eq 0 ]; then
        log "证书签发成功！"
        generate_ssl_nginx_config
        nginx -s reload
        log "Nginx 已重载，HTTPS 已启用"
    else
        log "证书签发失败"
        exit 1
    fi
}

renew_certificate() {
    log "开始续期 SSL 证书..."

    certbot renew --quiet --webroot --webroot-path="${WEBROOT_PATH}"

    if [ $? -eq 0 ]; then
        log "证书续期检查完成"
        # 如果有域名配置，重新生成配置并重载
        if [ -n "${SSL_DOMAIN}" ]; then
            generate_ssl_nginx_config
            nginx -s reload
            log "Nginx 已重载"
        fi
    else
        log "证书续期失败"
    fi
}

start_cron_renewal() {
    log "启动证书自动续期（每12小时检查一次）..."
    while true; do
        sleep 43200  # 12小时
        renew_certificate
    done
}

init_ssl() {
    # 初始化：确保 SSL 配置文件存在
    mkdir -p "${SSL_CONF_DIR}"

    if [ -z "${SSL_DOMAIN}" ]; then
        log "未设置 SSL_DOMAIN，以纯 HTTP 模式运行"
        clear_ssl_nginx_config
        return
    fi

    # 检查证书是否已存在（使用第一个域名作为主域名查找证书）
    local primary_domain
    primary_domain=$(get_primary_domain)
    local cert_path="/etc/letsencrypt/live/${primary_domain}"
    if [ -f "${cert_path}/fullchain.pem" ]; then
        log "检测到已有证书: ${primary_domain}，启用 HTTPS（域名: $(get_all_domains_space)）"
        generate_ssl_nginx_config
    else
        log "未检测到证书，以 HTTP 模式启动。请运行 'docker exec <容器名> /ssl-renew.sh issue' 签发证书"
        clear_ssl_nginx_config
    fi
}

case "${1:-init}" in
    issue)
        issue_certificate
        ;;
    renew)
        renew_certificate
        ;;
    cron)
        start_cron_renewal
        ;;
    init)
        init_ssl
        ;;
    *)
        echo "用法: $0 {issue|renew|cron|init}"
        echo "  init  - 初始化 SSL 配置（启动时自动调用）"
        echo "  issue - 首次签发证书"
        echo "  renew - 手动续期证书"
        echo "  cron  - 启动自动续期（后台运行）"
        exit 1
        ;;
esac


