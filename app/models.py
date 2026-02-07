"""
数据模型定义
"""
from typing import Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime


class ProxyRule(BaseModel):
    """代理规则模型"""
    id: Optional[str] = None
    path: str = Field(..., description="URL路径，如 /api")
    target_port: int = Field(..., ge=1, le=65535, description="目标端口")
    target_host: str = Field(default="localhost", description="目标主机")
    enabled: bool = Field(default=True, description="是否启用")
    health_check_path: Optional[str] = Field(default=None, description="健康检查路径")
    description: Optional[str] = Field(default="", description="规则描述")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @validator('path')
    def validate_path(cls, v):
        """验证路径格式"""
        if not v.startswith('/'):
            raise ValueError('路径必须以 / 开头')
        if ' ' in v:
            raise ValueError('路径不能包含空格')
        return v

    @validator('health_check_path')
    def validate_health_check_path(cls, v):
        """验证健康检查路径格式"""
        if v is not None and not v.startswith('/'):
            raise ValueError('健康检查路径必须以 / 开头')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "path": "/api",
                "target_port": 8001,
                "target_host": "localhost",
                "enabled": True,
                "health_check_path": "/health",
                "description": "API 服务"
            }
        }


class ProxyRuleCreate(BaseModel):
    """创建代理规则的请求模型"""
    path: str = Field(..., description="URL路径")
    target_port: int = Field(..., ge=1, le=65535, description="目标端口")
    target_host: str = Field(default="localhost", description="目标主机")
    enabled: bool = Field(default=True, description="是否启用")
    health_check_path: Optional[str] = Field(default=None, description="健康检查路径")
    description: Optional[str] = Field(default="", description="规则描述")

    @validator('path')
    def validate_path(cls, v):
        if not v.startswith('/'):
            raise ValueError('路径必须以 / 开头')
        if ' ' in v:
            raise ValueError('路径不能包含空格')
        return v


class ProxyRuleUpdate(BaseModel):
    """更新代理规则的请求模型"""
    path: Optional[str] = None
    target_port: Optional[int] = Field(default=None, ge=1, le=65535)
    target_host: Optional[str] = None
    enabled: Optional[bool] = None
    health_check_path: Optional[str] = None
    description: Optional[str] = None

    @validator('path')
    def validate_path(cls, v):
        if v is not None and not v.startswith('/'):
            raise ValueError('路径必须以 / 开头')
        return v


class HealthCheckResult(BaseModel):
    """健康检查结果模型"""
    rule_id: str
    path: str
    target_url: str
    status: str = Field(..., description="状态: healthy, unhealthy, unknown")
    response_time_ms: Optional[float] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    last_check_time: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "rule_id": "1",
                "path": "/api",
                "target_url": "http://localhost:8001/health",
                "status": "healthy",
                "response_time_ms": 15.5,
                "status_code": 200,
                "last_check_time": "2026-02-07T11:45:00"
            }
        }


class NginxReloadResponse(BaseModel):
    """Nginx重载响应模型"""
    success: bool
    message: str
    config_path: Optional[str] = None
    error: Optional[str] = None


class APIResponse(BaseModel):
    """通用API响应模型"""
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None
