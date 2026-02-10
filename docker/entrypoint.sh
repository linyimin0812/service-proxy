#!/bin/bash

echo "=========================================="
echo "NGINX 代理配置管理系统 - 容器启动"
echo "=========================================="

# 初始化配置目录（以 root 身份执行，确保权限正确）
echo "[1/3] 初始化配置目录..."
mkdir -p /app/config/backups
mkdir -p /app/nginx

# 创建默认配置文件（如果不存在）
if [ ! -f /app/config/proxy_config.yaml ]; then
    echo "[2/3] 创建默认配置文件..."
    cat > /app/config/proxy_config.yaml << 'EOF'
rules: []
EOF
    echo "✓ 默认配置文件已创建"
else
    echo "[2/3] 配置文件已存在，跳过创建"
fi

# 初始化 Nginx 配置文件
echo "[3/3] 初始化 Nginx 配置文件..."
if [ ! -f /app/nginx/proxy_rules.conf ]; then
    cat > /app/nginx/proxy_rules.conf << 'EOF'
# NGINX 代理规则配置
# 自动生成，请勿手动编辑
EOF
    echo "✓ Nginx 配置文件已创建"
else
    echo "✓ Nginx 配置文件已存在"
fi

# 修复挂载卷的权限，确保 appuser 可读写
echo "[*] 修复文件权限..."
chown -R appuser:appuser /app/config
chown -R appuser:appuser /app/nginx
echo "✓ 文件权限已修复"

echo "=========================================="
echo "初始化完成，以 appuser 身份启动应用..."
echo "=========================================="

# 以 appuser 身份执行传入的命令
exec gosu appuser "$@"


