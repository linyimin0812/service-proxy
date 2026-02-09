#!/bin/bash

echo "=========================================="
echo "NGINX 代理配置管理系统 - 容器启动"
echo "=========================================="

# 初始化配置目录
echo "[1/3] 初始化配置目录..."
mkdir -p /app/config/backups 2>/dev/null || true
mkdir -p /app/nginx 2>/dev/null || true

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
    if [ $? -eq 0 ]; then
        echo "✓ Nginx 配置文件已创建"
    else
        echo "⚠ 无法创建配置文件，应用启动后将自动创建"
    fi
else
    echo "✓ Nginx 配置文件已存在"
    # 验证文件可写
    if [ -w /app/nginx/proxy_rules.conf ]; then
        echo "✓ 配置文件可写"
    else
        echo "⚠ 配置文件不可写，应用运行时可能出现写入错误"
        echo "  建议在宿主机执行: chmod 666 nginx/proxy_rules.conf"
    fi
fi

echo "=========================================="
echo "初始化完成，启动应用..."
echo "=========================================="

# 执行传入的命令
exec "$@"

