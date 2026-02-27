"""
NGINX 代理配置管理系统 - FastAPI 主应用
"""
import os
import logging
import sys
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from app.api.routes import router
from app.health_check import health_checker

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

ACCESS_TOKEN = os.getenv('ACCESS_TOKEN', 'changeme')

PUBLIC_PATHS = ['/health', '/api/auth/verify', '/api/monitor', '/assets']


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Token 验证中间件，保护所有 API 和页面访问"""

    async def dispatch(self, request: Request, call_next):
        request_path = request.url.path

        for public_path in PUBLIC_PATHS:
            if request_path == public_path or request_path.startswith(public_path + '/'):
                return await call_next(request)

        if request_path == '/' or request_path == '/admin' or request_path.startswith('/static'):
            return await call_next(request)

        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        else:
            token = request.query_params.get('token', '')

        if token != ACCESS_TOKEN:
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权访问，请提供有效的 Token"}
            )

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("启动健康检查服务...")
    logger.info("Token 验证已启用")
    health_checker.start()

    yield

    logger.info("停止健康检查服务...")
    health_checker.stop()

# 创建 FastAPI 应用
app = FastAPI(
    title="NGINX 代理配置管理系统",
    description="通过 Web 界面管理 NGINX 反向代理配置",
    version="1.0.0",
    lifespan=lifespan
)

# 添加 Token 验证中间件
app.add_middleware(TokenAuthMiddleware)

# 注册 API 路由
app.include_router(router)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def home():
    """返回博客首页"""
    return FileResponse("static/home.html")

@app.get("/admin")
async def admin():
    """返回管理页面"""
    return FileResponse("static/index.html")


@app.post("/api/auth/verify")
async def verify_token(request: Request):
    """验证 Token 是否正确"""
    try:
        body = await request.json()
        token = body.get('token', '')
    except Exception:
        token = ''

    if token == ACCESS_TOKEN:
        return {"success": True, "message": "Token 验证成功"}
    else:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Token 无效"}
        )


@app.get("/health")
async def health():
    """应用健康检查端点"""
    return {"status": "healthy", "service": "nginx-proxy-manager"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


