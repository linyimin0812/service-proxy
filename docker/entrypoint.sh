#!/bin/bash
set -e

echo "=========================================="
echo "NGINX 代理配置管理系统 - 容器启动"
echo "=========================================="

# 初始化配置目录
echo "[1/4] 初始化配置目录..."
mkdir -p /app/config/backups

# 创建默认配置文件（如果不存在）
if [ ! -f /app/config/proxy_config.yaml ]; then
    echo "[2/4] 创建默认配置文件..."
    cat > /app/config/proxy_config.yaml << 'EOF'
rules: []
EOF
    echo "默认配置文件已创建"
else
    echo "[2/4] 配置文件已存在，跳过创建"
fi

# 等待 Nginx 容器就绪（如果需要）
echo "[3/4] 检查 Nginx 容器..."
if [ -n "$NGINX_CONTAINER_NAME" ]; then
    echo "等待 Nginx 容器 $NGINX_CONTAINER_NAME 就绪..."
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${NGINX_CONTAINER_NAME}$"; then
            echo "Nginx 容器已就绪"
            break
        fi
        attempt=$((attempt + 1))
        echo "等待中... ($attempt/$max_attempts)"
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        echo "警告: Nginx 容器未在预期时间内就绪，继续启动..."
    fi
else
    echo "未配置 NGINX_CONTAINER_NAME，跳过检查"
fi

# 创建空的 Nginx 代理规则文件（如果不存在）
echo "[4/4] 初始化 Nginx 配置..."
NGINX_CONF_DIR="/etc/nginx/conf.d"

# 通过 Docker socket 在 Nginx 容器中创建配置文件
if [ -n "$NGINX_CONTAINER_NAME" ] && docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${NGINX_CONTAINER_NAME}$"; then
    docker exec "$NGINX_CONTAINER_NAME" sh -c "touch $NGINX_CONF_DIR/proxy_rules.conf" 2>/dev/null || true
    echo "Nginx 代理规则配置文件已初始化"
fi

echo "=========================================="
echo "初始化完成，启动应用..."
echo "=========================================="

# 执行传入的命令
exec "$@"
