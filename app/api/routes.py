"""
API 路由定义
"""
from typing import List
from fastapi import APIRouter, HTTPException, status
from app.models import (
    ProxyRule,
    ProxyRuleCreate,
    ProxyRuleUpdate,
    HealthCheckResult,
    NginxReloadResponse,
    APIResponse
)
from app.config_manager import ConfigManager
from app.nginx_manager import NginxManager
from app.health_check import health_checker


router = APIRouter(prefix="/api", tags=["proxy"])

# 初始化管理器
config_manager = ConfigManager()
nginx_manager = NginxManager()


@router.get("/rules", response_model=List[ProxyRule])
async def get_all_rules():
    """获取所有代理规则"""
    try:
        rules = config_manager.get_all_rules()
        return rules
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取规则失败: {str(e)}"
        )


@router.get("/rules/{rule_id}", response_model=ProxyRule)
async def get_rule(rule_id: str):
    """获取指定ID的代理规则"""
    rule = config_manager.get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"规则 {rule_id} 不存在"
        )
    return rule


@router.post("/rules", response_model=ProxyRule, status_code=status.HTTP_201_CREATED)
async def create_rule(rule_data: ProxyRuleCreate):
    """创建新的代理规则"""
    try:
        # 检查路径是否已存在
        existing_rule = config_manager.get_rule_by_path(rule_data.path)
        if existing_rule:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"路径 {rule_data.path} 已存在"
            )
        
        # 创建规则
        rule = ProxyRule(**rule_data.model_dump())
        created_rule = config_manager.add_rule(rule)
        
        return created_rule
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建规则失败: {str(e)}"
        )


@router.put("/rules/{rule_id}", response_model=ProxyRule)
async def update_rule(rule_id: str, rule_data: ProxyRuleUpdate):
    """更新代理规则"""
    try:
        # 检查规则是否存在
        existing_rule = config_manager.get_rule_by_id(rule_id)
        if not existing_rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"规则 {rule_id} 不存在"
            )
        
        # 更新规则
        updates = rule_data.model_dump(exclude_none=True)
        updated_rule = config_manager.update_rule(rule_id, updates)
        
        return updated_rule
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新规则失败: {str(e)}"
        )


@router.delete("/rules/{rule_id}", response_model=APIResponse)
async def delete_rule(rule_id: str):
    """删除代理规则"""
    try:
        config_manager.delete_rule(rule_id)
        return APIResponse(
            success=True,
            message=f"规则 {rule_id} 已删除"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除规则失败: {str(e)}"
        )


@router.post("/reload", response_model=NginxReloadResponse)
async def reload_nginx():
    """重载 Nginx 配置"""
    try:
        result = nginx_manager.update_and_reload()
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error or result.message
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重载 Nginx 失败: {str(e)}"
        )


@router.get("/health", response_model=dict)
async def get_health_status(rule_id: str = None):
    """获取健康检查状态"""
    try:
        if rule_id:
            status_data = health_checker.get_health_status(rule_id)
            if "error" in status_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=status_data["error"]
                )
            return status_data
        else:
            return health_checker.get_health_status()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取健康状态失败: {str(e)}"
        )


@router.get("/health/statistics", response_model=dict)
async def get_health_statistics():
    """获取健康检查统计信息"""
    try:
        return health_checker.get_statistics()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )


@router.post("/health/check", response_model=List[HealthCheckResult])
async def trigger_health_check():
    """手动触发健康检查"""
    try:
        results = await health_checker.check_all_rules()
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"健康检查失败: {str(e)}"
        )


@router.get("/nginx/status", response_model=dict)
async def get_nginx_status():
    """获取 Nginx 状态信息"""
    try:
        return nginx_manager.get_nginx_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 Nginx 状态失败: {str(e)}"
        )


@router.get("/config/validate", response_model=APIResponse)
async def validate_config():
    """验证配置文件"""
    try:
        is_valid, error = config_manager.validate_config()
        
        if is_valid:
            return APIResponse(
                success=True,
                message="配置文件验证通过"
            )
        else:
            return APIResponse(
                success=False,
                message="配置文件验证失败",
                error=error
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"验证配置失败: {str(e)}"
        )


@router.get("/config/backups", response_model=List[dict])
async def list_backups():
    """列出所有配置备份"""
    try:
        return config_manager.list_backups()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取备份列表失败: {str(e)}"
        )


@router.post("/config/restore/{backup_filename}", response_model=APIResponse)
async def restore_backup(backup_filename: str):
    """从备份恢复配置"""
    try:
        config_manager.restore_from_backup(backup_filename)
        return APIResponse(
            success=True,
            message=f"已从备份 {backup_filename} 恢复配置"
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复备份失败: {str(e)}"
        )
