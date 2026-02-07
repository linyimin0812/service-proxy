"""
健康检查模块
定期检查后端服务的健康状态
使用 TCP 端口检查替代 HTTP 检查
"""
import asyncio
from typing import Dict, List
from datetime import datetime
from app.models import ProxyRule, HealthCheckResult
from app.config_manager import ConfigManager


class HealthChecker:
    """健康检查器"""
    
    def __init__(self, timeout: int = 5, check_interval: int = 30):
        """
        初始化健康检查器
        
        Args:
            timeout: TCP 连接超时时间（秒）
            check_interval: 检查间隔时间（秒）
        """
        self.timeout = timeout
        self.check_interval = check_interval
        self.config_manager = ConfigManager()
        self.health_status: Dict[str, HealthCheckResult] = {}
        self._running = False
        self._task = None
    
    async def check_single_rule(self, rule: ProxyRule) -> HealthCheckResult:
        """
        检查单个规则的健康状态（使用 TCP 端口检查）
        
        Args:
            rule: 代理规则
            
        Returns:
            健康检查结果
        """
        # 构建目标地址
        target_url = f"tcp://{rule.target_host}:{rule.target_port}"
        
        result = HealthCheckResult(
            rule_id=rule.id,
            path=rule.path,
            target_url=target_url,
            status="unknown",
            last_check_time=datetime.now()
        )
        
        try:
            start_time = datetime.now()
            
            # 使用 asyncio.open_connection 进行 TCP 连接测试
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(rule.target_host, rule.target_port),
                timeout=self.timeout
            )
            
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds() * 1000
            
            # 关闭连接
            writer.close()
            await writer.wait_closed()
            
            result.response_time_ms = round(response_time, 2)
            result.status_code = None  # TCP 检查不返回状态码
            result.status = "healthy"
                
        except asyncio.TimeoutError:
            result.status = "unhealthy"
            result.error_message = "连接超时"
        except ConnectionRefusedError:
            result.status = "unhealthy"
            result.error_message = "连接被拒绝"
        except OSError as e:
            result.status = "unhealthy"
            result.error_message = f"连接失败: {str(e)}"
        except Exception as e:
            result.status = "unhealthy"
            result.error_message = str(e)
        
        return result
    
    async def check_all_rules(self) -> List[HealthCheckResult]:
        """
        检查所有启用的规则
        
        Returns:
            所有规则的健康检查结果列表
        """
        rules = self.config_manager.get_enabled_rules()
        
        # 并发检查所有规则
        tasks = [self.check_single_rule(rule) for rule in rules]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 更新健康状态缓存
        for result in results:
            if isinstance(result, HealthCheckResult):
                self.health_status[result.rule_id] = result
        
        return [r for r in results if isinstance(r, HealthCheckResult)]
    
    async def _check_loop(self):
        """健康检查循环"""
        while self._running:
            try:
                await self.check_all_rules()
            except Exception as e:
                print(f"健康检查异常: {e}")
            
            # 等待下一次检查
            await asyncio.sleep(self.check_interval)
    
    def start(self):
        """启动健康检查"""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._check_loop())
    
    def stop(self):
        """停止健康检查"""
        self._running = False
        if self._task:
            self._task.cancel()
    
    def get_health_status(self, rule_id: str = None) -> Dict:
        """
        获取健康状态
        
        Args:
            rule_id: 规则ID，如果为 None 则返回所有规则的状态
            
        Returns:
            健康状态字典
        """
        if rule_id:
            result = self.health_status.get(rule_id)
            if result:
                return result.model_dump()
            else:
                return {"error": f"规则 {rule_id} 未找到或未检查"}
        else:
            return {
                rule_id: result.model_dump()
                for rule_id, result in self.health_status.items()
            }
    
    def get_unhealthy_rules(self) -> List[HealthCheckResult]:
        """获取所有不健康的规则"""
        return [
            result for result in self.health_status.values()
            if result.status == "unhealthy"
        ]
    
    def get_healthy_rules(self) -> List[HealthCheckResult]:
        """获取所有健康的规则"""
        return [
            result for result in self.health_status.values()
            if result.status == "healthy"
        ]
    
    def get_statistics(self) -> Dict:
        """获取健康检查统计信息"""
        total = len(self.health_status)
        healthy = len(self.get_healthy_rules())
        unhealthy = len(self.get_unhealthy_rules())
        unknown = total - healthy - unhealthy
        
        # 计算平均响应时间
        response_times = [
            result.response_time_ms
            for result in self.health_status.values()
            if result.response_time_ms is not None
        ]
        avg_response_time = (
            round(sum(response_times) / len(response_times), 2)
            if response_times else None
        )
        
        return {
            "total": total,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "unknown": unknown,
            "health_rate": round(healthy / total * 100, 2) if total > 0 else 0,
            "avg_response_time_ms": avg_response_time,
            "last_check_time": max(
                (result.last_check_time for result in self.health_status.values()),
                default=None
            )
        }


# 全局健康检查器实例
health_checker = HealthChecker()
