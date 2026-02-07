# Docker 部署指南

本文档介绍如何使用 Docker Compose 部署 NGINX 代理配置管理系统。

## 系统要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB 可用内存
- 至少 5GB 可用磁盘空间

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd FastAPIProject
```

### 2. 构建并启动服务

```bash
# 构建镜像
docker-compose build

# 启动服务（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 3. 访问服务

- **管理界面**: http://localhost
- **API 文档**: http://localhost/docs
- **健康检查**: http://localhost/health

### 4. 验证部署

```bash
# 检查服务状态
docker-compose ps

# 应该看到两个服务都在运行：
# - nginx-proxy-manager-nginx
# - nginx-proxy-manager-fastapi
```

## 服务架构

```
┌─────────────────────────────────────┐
│         Docker Network              │
│      (nginx-proxy-network)          │
│                                     │
│  ┌──────────┐      ┌──────────┐   │
│  │  Nginx   │─────▶│ FastAPI  │   │
│  │ (80端口) │      │(8000端口)│   │
│  └──────────┘      └──────────┘   │
│       │                             │
└───────┼─────────────────────────────┘
        │
        ▼
   外部访问 (80端口)
```

## 配置说明

### 环境变量

可以通过环境变量自定义配置：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `PYTHONUNBUFFERED` | 1 | Python 输出不缓冲 |
| `CONFIG_PATH` | /app/config | 配置文件路径 |
| `NGINX_CONTAINER_NAME` | nginx-proxy-manager-nginx | Nginx 容器名称 |

创建 `.env` 文件自定义配置：

```bash
# .env
NGINX_CONTAINER_NAME=my-nginx
CONFIG_PATH=/app/config
```

### Volume 说明

系统使用以下 Docker volumes 持久化数据：

- **nginx-proxy-config**: 代理配置文件和备份
- **nginx-proxy-conf**: Nginx 配置文件
- **nginx-proxy-logs**: Nginx 日志文件

## 常用操作

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看 FastAPI 服务日志
docker-compose logs -f fastapi

# 查看 Nginx 服务日志
docker-compose logs -f nginx

# 查看最近 100 行日志
docker-compose logs --tail=100
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart fastapi
docker-compose restart nginx
```

### 停止服务

```bash
# 停止服务（保留容器）
docker-compose stop

# 停止并删除容器
docker-compose down

# 停止并删除容器和 volumes（会删除所有数据）
docker-compose down -v
```

### 更新部署

```bash
# 1. 拉取最新代码
git pull

# 2. 重新构建镜像
docker-compose build

# 3. 重启服务
docker-compose up -d

# 4. 清理旧镜像
docker image prune -f
```

### 扩容服务

```bash
# 扩展 FastAPI 服务实例（需要配置负载均衡）
docker-compose up -d --scale fastapi=3
```

## 数据管理

### 备份配置

```bash
# 备份配置文件
docker run --rm \
  -v nginx-proxy-config:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/config-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .

# 备份 Nginx 配置
docker run --rm \
  -v nginx-proxy-conf:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/nginx-conf-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
```

### 恢复配置

```bash
# 恢复配置文件
docker run --rm \
  -v nginx-proxy-config:/data \
  -v $(pwd)/backup:/backup \
  alpine sh -c "cd /data && tar xzf /backup/config-YYYYMMDD-HHMMSS.tar.gz"

# 重启服务使配置生效
docker-compose restart
```

### 查看 Volume 内容

```bash
# 列出所有 volumes
docker volume ls | grep nginx-proxy

# 查看 volume 详情
docker volume inspect nginx-proxy-config

# 进入容器查看文件
docker-compose exec fastapi ls -la /app/config
```

## 故障排查

### 问题：容器无法启动

**检查步骤**：

```bash
# 1. 查看容器状态
docker-compose ps

# 2. 查看详细日志
docker-compose logs fastapi
docker-compose logs nginx

# 3. 检查端口占用
sudo netstat -tlnp | grep :80

# 4. 检查 Docker 资源
docker system df
```

**常见原因**：
- 端口 80 被占用
- 磁盘空间不足
- 内存不足
- 配置文件错误

### 问题：Nginx 重载失败

**检查步骤**：

```bash
# 1. 检查 Nginx 配置语法
docker-compose exec nginx nginx -t

# 2. 查看 Nginx 错误日志
docker-compose exec nginx cat /var/log/nginx/error.log

# 3. 检查生成的配置文件
docker-compose exec nginx cat /etc/nginx/conf.d/proxy_rules.conf
```

**解决方案**：
- 检查代理规则配置是否正确
- 确认目标端口服务是否可达
- 查看 FastAPI 日志了解配置生成过程

### 问题：无法访问管理页面

**检查步骤**：

```bash
# 1. 检查服务健康状态
docker-compose ps

# 2. 测试 FastAPI 服务
docker-compose exec fastapi curl http://localhost:8000/health

# 3. 测试 Nginx 转发
curl http://localhost/health

# 4. 检查网络连接
docker network inspect nginx-proxy-network
```

### 问题：配置文件丢失

**解决方案**：

```bash
# 1. 检查 volume 是否存在
docker volume ls | grep nginx-proxy-config

# 2. 如果 volume 被删除，从备份恢复
# （参考"恢复配置"章节）

# 3. 如果没有备份，重新初始化
docker-compose down -v
docker-compose up -d
```

## 性能优化

### 资源限制

在 `docker-compose.yml` 中添加资源限制：

```yaml
services:
  fastapi:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
  
  nginx:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

### 日志轮转

配置日志大小限制（已在 docker-compose.yml 中配置）：

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### 网络优化

```bash
# 查看网络延迟
docker-compose exec fastapi ping nginx

# 优化 DNS 解析
# 在 docker-compose.yml 中添加：
services:
  fastapi:
    dns:
      - 8.8.8.8
      - 8.8.4.4
```

## 监控和告警

### 健康检查

系统内置健康检查（使用 TCP 端口检查）：

```bash
# 手动测试 TCP 端口检查
# 测试 FastAPI 服务端口
   docker-compose exec fastapi nc -z localhost 8000
   echo $?  # 返回 0 表示端口开放
   
   # 测试 Nginx 服务端口
   docker-compose exec nginx nc -z localhost 80
   echo $?  # 返回 0 表示端口开放

# HTTP 健康检查端点（仍然可用）
curl http://localhost/health

# 查看容器健康检查状态
docker inspect nginx-proxy-manager-fastapi | grep -A 10 Health
docker inspect nginx-proxy-manager-nginx | grep -A 10 Health
```

**健康检查说明**：
- Docker 容器级别使用 TCP 端口检查（更轻量、更快速）
- HTTP `/health` 端点仍然保留，供外部监控系统使用
- 应用内部服务间检查也使用 TCP 端口检查

### 日志监控

使用外部日志收集工具（如 ELK、Loki）：

```yaml
# docker-compose.yml
services:
  fastapi:
    logging:
      driver: "syslog"
      options:
        syslog-address: "tcp://logstash:5000"
```

### 指标收集

集成 Prometheus 监控：

```yaml
# 添加 Prometheus exporter
services:
  nginx-exporter:
    image: nginx/nginx-prometheus-exporter
    command:
      - '-nginx.scrape-uri=http://nginx/stub_status'
    ports:
      - "9113:9113"
```

## 安全建议

### 1. 网络隔离

```yaml
# 创建独立的前端和后端网络
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # 后端网络不可访问外部
```

### 2. 使用 Secrets

```yaml
# 使用 Docker secrets 管理敏感信息
secrets:
  api_key:
    file: ./secrets/api_key.txt

services:
  fastapi:
    secrets:
      - api_key
```

### 3. 定期更新

```bash
# 更新基础镜像
docker-compose pull
docker-compose build --no-cache
docker-compose up -d
```

### 4. 限制容器权限

```yaml
services:
  fastapi:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

## 生产环境部署

### 使用 Docker Swarm

```bash
# 初始化 Swarm
docker swarm init

# 部署 stack
docker stack deploy -c docker-compose.yml nginx-proxy

# 查看服务
docker stack services nginx-proxy

# 扩容服务
docker service scale nginx-proxy_fastapi=3
```

### 使用 Kubernetes

参考 `k8s/` 目录下的 Kubernetes 配置文件（如果提供）。

## 常见问题

**Q: 如何修改 Nginx 监听端口？**

A: 修改 `docker-compose.yml` 中的端口映射：

```yaml
nginx:
  ports:
    - "8080:80"  # 改为 8080 端口
```

**Q: 如何启用 HTTPS？**

A: 需要配置 SSL 证书，参考主 README 的 SSL 配置章节。

**Q: 如何查看容器内的文件？**

A: 使用 `docker-compose exec` 进入容器：

```bash
docker-compose exec fastapi bash
docker-compose exec nginx sh
```

**Q: 如何清理所有数据重新开始？**

A: 执行以下命令：

```bash
docker-compose down -v
docker system prune -a
docker-compose up -d
```

## 技术支持

- 项目地址: https://github.com/your-repo/nginx-proxy-manager
- 问题反馈: https://github.com/your-repo/nginx-proxy-manager/issues
- 文档: https://github.com/your-repo/nginx-proxy-manager/wiki
