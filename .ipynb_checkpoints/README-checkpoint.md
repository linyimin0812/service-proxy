# NGINX 代理配置管理系统

一个基于 FastAPI + Nginx 的代理配置管理系统，通过 Web 界面管理 NGINX 反向代理配置，支持动态更新和健康检查。

## 功能特性

- ✅ Web 界面管理代理规则
- ✅ 支持添加、编辑、删除代理规则
- ✅ 自动生成 Nginx 配置文件
- ✅ 一键重载 Nginx 配置
- ✅ 后端服务健康检查
- ✅ 配置文件备份与恢复
- ✅ 实时统计信息展示

## 系统架构

```
┌─────────────┐
│   浏览器     │
│  (80端口)    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Nginx    │  ← 反向代理 (80端口对外)
│  (80端口)    │
└──────┬──────┘
       │
       ├─────────────────────────────┐
       │                             │
       ▼                             ▼
┌─────────────┐              ┌─────────────┐
│   FastAPI   │              │  后端服务1   │
│ 管理系统     │              │  (8001端口)  │
│ (8000端口)  │              └─────────────┘
└─────────────┘                     │
       │                             ▼
       │                      ┌─────────────┐
       │                      │  后端服务2   │
       │                      │  (8002端口)  │
       │                      └─────────────┘
       │                             │
       └─────────────────────────────┘
              健康检查
```

## 项目结构

```
FastAPIProject/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── models.py            # 数据模型
│   ├── config_manager.py    # 配置文件管理
│   ├── nginx_manager.py     # Nginx 配置生成和重载
│   ├── health_check.py      # 健康检查模块
│   └── api/
│       ├── __init__.py
│       └── routes.py        # API 路由
├── static/
│   └── index.html           # Web 管理页面
├── config/
│   ├── proxy_config.yaml    # 代理配置文件
│   └── backups/             # 配置备份目录
├── nginx/
│   └── nginx.conf.template  # Nginx 配置模板
├── main.py                  # 应用启动入口
├── pyproject.toml           # 项目依赖配置
└── README.md                # 项目文档
```

## 快速开始

### 方式一：Docker Compose 部署（推荐）

使用 Docker Compose 可以快速部署完整的系统，无需手动配置 Nginx。

```bash
# 1. 构建并启动服务
docker-compose up -d

# 2. 查看服务状态
docker-compose ps

# 3. 查看日志
docker-compose logs -f


# 4. 启动jupyter
python3 -m venv ~/jupyter-venv
source ~/jupyter-venv/bin/activate
pip install jupyterlab
nohup jupyter lab --ip=0.0.0.0 --port=8080 --no-browser --allow-root --ServerApp.base_url='/jupyter' --ServerApp.allow_origin='*' --ServerApp.allow_remote_access=True --ServerApp.trust_xheaders=True --notebook-dir=/root/ > /var/log/jupyter.log 2>&1 &

# 5. 启动kubectl proxy
nohup kubectl proxy --address 0.0.0.0 --port 8001 --accept-hosts '.*' > /var/log/kubectl-proxy.log 2>&1 &

```

**访问服务**：
- 管理界面：http://localhost
- API 文档：http://localhost/docs
- 健康检查：http://localhost/health

**常用命令**：
```bash
# 停止服务
docker-compose stop

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f fastapi
docker-compose logs -f nginx

# 更新部署
git pull
docker-compose build
docker-compose up -d
```

📖 **详细文档**：查看 [Docker 部署指南](docs/DOCKER_DEPLOYMENT.md) 了解更多配置选项、故障排查和最佳实践。

---

### 方式二：本地部署

#### 1. 安装依赖

使用 uv（推荐）：
```bash
uv sync
```

或使用 pip：
```bash
pip install -e .
```

#### 2. 启动 FastAPI 服务

```bash
python main.py
```

服务将在 `http://localhost:8000` 启动。

#### 3. 访问管理界面

打开浏览器访问：`http://localhost:8000`

#### 4. 配置 Nginx

#### 方式一：手动配置（开发环境）

1. 创建 Nginx 主配置文件 `/etc/nginx/nginx.conf`（如果不存在）

2. 在 Nginx 配置中添加以下内容：

```nginx
http {
    # ... 其他配置 ...

    # 管理页面代理
    server {
        listen 80;
        server_name localhost;

        # 代理管理界面到 FastAPI
        location /admin/proxy-manager {
            proxy_pass http://localhost:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # 引入动态生成的代理规则
        include /etc/nginx/conf.d/proxy_rules.conf;
    }
}
```

3. 确保 FastAPI 进程有权限执行 Nginx 重载：

```bash
# 添加 sudo 权限（仅用于开发环境）
sudo visudo

# 添加以下行（替换 your_username）
your_username ALL=(ALL) NOPASSWD: /usr/sbin/nginx -s reload
your_username ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t
```

#### 方式二：使用部署脚本（生产环境）

```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

## 使用说明

### 添加代理规则

1. 点击"添加规则"按钮
2. 填写以下信息：
   - **路径**：URL 路径，如 `/api`
   - **目标端口**：后端服务端口，如 `8001`
   - **目标主机**：后端服务主机，默认 `localhost`
   - **健康检查路径**：可选，如 `/health`
   - **描述**：规则描述
   - **启用状态**：是否启用此规则
3. 点击"保存"

### 编辑/删除规则

- 点击规则行的"编辑"按钮修改规则
- 点击"删除"按钮删除规则

### 重载 Nginx

修改规则后，点击"重载 Nginx"按钮应用配置。

### 健康检查

- 系统每 30 秒自动检查后端服务健康状态（使用 TCP 端口检查）
- 点击"健康检查"按钮可手动触发检查
- 健康状态会实时显示在规则列表中
- 检查方式：直接测试目标端口的连通性，更轻量、更快速

## API 文档

启动服务后访问：`http://localhost:8000/docs`

### 主要 API 端点

- `GET /api/rules` - 获取所有代理规则
- `POST /api/rules` - 创建新规则
- `PUT /api/rules/{rule_id}` - 更新规则
- `DELETE /api/rules/{rule_id}` - 删除规则
- `POST /api/reload` - 重载 Nginx 配置
- `GET /api/health` - 获取健康检查状态
- `POST /api/health/check` - 手动触发健康检查
- `GET /api/health/statistics` - 获取统计信息

## 配置文件格式

配置文件位于 `config/proxy_config.yaml`：

```yaml
rules:
  - id: "1"
    path: /api
    target_port: 8001
    target_host: localhost
    enabled: true
    description: "API 服务"
    created_at: "2026-02-07T11:45:00"
    updated_at: "2026-02-07T11:45:00"
```

## 安全建议

### 生产环境部署

1. **添加认证**：为管理页面添加基本认证或 OAuth
2. **限制访问**：使用防火墙限制管理端口访问
3. **HTTPS**：配置 SSL/TLS 证书
4. **权限控制**：使用专用用户运行服务，限制文件权限
5. **日志审计**：记录所有配置变更操作

### 权限配置

```bash
# 创建专用用户
sudo useradd -r -s /bin/false nginx-manager

# 设置文件权限
sudo chown -R nginx-manager:nginx-manager /path/to/FastAPIProject
sudo chmod 750 /path/to/FastAPIProject/config

# 配置 sudo 权限
sudo visudo
# 添加：
nginx-manager ALL=(ALL) NOPASSWD: /usr/sbin/nginx -s reload
nginx-manager ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t
```

## 故障排查

### 问题：Nginx 重载失败

**解决方案**：
1. 检查 Nginx 配置语法：`sudo nginx -t`
2. 查看 Nginx 错误日志：`sudo tail -f /var/log/nginx/error.log`
3. 确认进程有 sudo 权限执行 nginx 命令

### 问题：健康检查失败

**解决方案**：
1. 确认后端服务正在运行
2. 检查端口是否正确
3. 验证健康检查路径是否存在
4. 查看 FastAPI 日志

### 问题：配置文件损坏

**解决方案**：
1. 查看备份列表：访问 `/api/config/backups`
2. 恢复备份：`POST /api/config/restore/{backup_filename}`

## 开发

### 运行测试

```bash
# 安装开发依赖
pip install pytest pytest-asyncio httpx

# 运行测试
pytest
```

### 代码格式化

```bash
pip install black isort
black .
isort .
```

## 技术栈

- **后端框架**：FastAPI 0.128+
- **Web 服务器**：Uvicorn
- **反向代理**：Nginx
- **配置格式**：YAML
- **模板引擎**：Jinja2
- **HTTP 客户端**：httpx
- **数据验证**：Pydantic

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

- 项目地址：https://github.com/your-repo/nginx-proxy-manager
- 问题反馈：https://github.com/your-repo/nginx-proxy-manager/issues
