#!/bin/bash

# NGINX 代理配置管理系统部署脚本
# 适用于 Linux 服务器环境

set -e

echo "=========================================="
echo "NGINX 代理配置管理系统 - 部署脚本"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}错误: 请使用 root 权限运行此脚本${NC}"
    echo "使用方法: sudo ./deploy.sh"
    exit 1
fi

# 配置变量
APP_USER="nginx-manager"
APP_DIR="/opt/nginx-proxy-manager"
NGINX_CONF_DIR="/etc/nginx/conf.d"
SYSTEMD_SERVICE="/etc/systemd/system/nginx-proxy-manager.service"
PYTHON_BIN="python3"

echo -e "${GREEN}[1/8] 检查系统依赖...${NC}"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 Python 3${NC}"
    echo "请先安装 Python 3: sudo apt-get install python3 python3-pip"
    exit 1
fi

# 检查 Nginx
if ! command -v nginx &> /dev/null; then
    echo -e "${YELLOW}警告: 未找到 Nginx，正在安装...${NC}"
    apt-get update
    apt-get install -y nginx
fi

echo -e "${GREEN}[2/8] 创建应用用户...${NC}"

# 创建应用用户（如果不存在）
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/false -d "$APP_DIR" "$APP_USER"
    echo "用户 $APP_USER 已创建"
else
    echo "用户 $APP_USER 已存在"
fi

echo -e "${GREEN}[3/8] 复制应用文件...${NC}"

# 创建应用目录
mkdir -p "$APP_DIR"

# 复制文件
cp -r app static config nginx main.py pyproject.toml "$APP_DIR/"

# 创建必要的目录
mkdir -p "$APP_DIR/config/backups"
mkdir -p "$NGINX_CONF_DIR"

# 设置文件权限
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 750 "$APP_DIR"
chmod 640 "$APP_DIR/config/proxy_config.yaml" 2>/dev/null || true

echo -e "${GREEN}[4/8] 安装 Python 依赖...${NC}"

# 安装依赖
cd "$APP_DIR"
pip3 install -e . || {
    echo -e "${RED}错误: 依赖安装失败${NC}"
    exit 1
}

echo -e "${GREEN}[5/8] 配置 Nginx...${NC}"

# 创建 Nginx 主配置
cat > /etc/nginx/sites-available/proxy-manager << 'EOF'
server {
    listen 80;
    server_name _;

    # 管理页面
    location /admin/proxy-manager {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API 接口
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态文件
    location /static {
        proxy_pass http://localhost:8000;
    }

    # 根路径重定向到管理页面
    location = / {
        proxy_pass http://localhost:8000;
    }

    # 引入动态生成的代理规则
    include /etc/nginx/conf.d/proxy_rules.conf;
}
EOF

# 启用站点
ln -sf /etc/nginx/sites-available/proxy-manager /etc/nginx/sites-enabled/

# 创建空的代理规则文件（如果不存在）
touch "$NGINX_CONF_DIR/proxy_rules.conf"

# 测试 Nginx 配置
nginx -t || {
    echo -e "${RED}错误: Nginx 配置测试失败${NC}"
    exit 1
}

echo -e "${GREEN}[6/8] 配置 sudo 权限...${NC}"

# 配置 sudo 权限
cat > /etc/sudoers.d/nginx-manager << EOF
# NGINX 代理配置管理系统权限
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/nginx -s reload
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t
EOF

chmod 440 /etc/sudoers.d/nginx-manager

echo -e "${GREEN}[7/8] 创建 systemd 服务...${NC}"

# 创建 systemd 服务文件
cat > "$SYSTEMD_SERVICE" << EOF
[Unit]
Description=NGINX Proxy Configuration Manager
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 $APP_DIR/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重载 systemd
systemctl daemon-reload

# 启用并启动服务
systemctl enable nginx-proxy-manager
systemctl start nginx-proxy-manager

# 重启 Nginx
systemctl restart nginx

echo -e "${GREEN}[8/8] 验证部署...${NC}"

# 等待服务启动
sleep 3

# 检查服务状态
if systemctl is-active --quiet nginx-proxy-manager; then
    echo -e "${GREEN}✓ FastAPI 服务运行正常${NC}"
else
    echo -e "${RED}✗ FastAPI 服务启动失败${NC}"
    echo "查看日志: journalctl -u nginx-proxy-manager -n 50"
    exit 1
fi

if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx 服务运行正常${NC}"
else
    echo -e "${RED}✗ Nginx 服务启动失败${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}部署完成！${NC}"
echo "=========================================="
echo ""
echo "访问地址："
echo "  - 管理页面: http://your-server-ip/"
echo "  - API 文档: http://your-server-ip:8000/docs"
echo ""
echo "常用命令："
echo "  - 查看服务状态: systemctl status nginx-proxy-manager"
echo "  - 查看日志: journalctl -u nginx-proxy-manager -f"
echo "  - 重启服务: systemctl restart nginx-proxy-manager"
echo "  - 停止服务: systemctl stop nginx-proxy-manager"
echo ""
echo "配置文件位置："
echo "  - 应用目录: $APP_DIR"
echo "  - 配置文件: $APP_DIR/config/proxy_config.yaml"
echo "  - Nginx 配置: $NGINX_CONF_DIR/proxy_rules.conf"
echo ""
echo -e "${YELLOW}注意: 首次使用请通过管理页面添加代理规则${NC}"
echo "=========================================="
