"""
NGINX 代理配置管理系统 - FastAPI 主应用
"""
import logging
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("启动健康检查服务...")
    health_checker.start()
    
    yield
    
    # 关闭时执行
    logger.info("停止健康检查服务...")
    health_checker.stop()


# 创建 FastAPI 应用
app = FastAPI(
    title="NGINX 代理配置管理系统",
    description="通过 Web 界面管理 NGINX 反向代理配置",
    version="1.0.0",
    lifespan=lifespan
)

# 注册 API 路由
app.include_router(router)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """返回管理页面"""
    return FileResponse("static/index.html")


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

