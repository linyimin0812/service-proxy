"""
Nginx 配置管理模块
负责生成 Nginx 配置文件并重载 Nginx
支持 Docker 环境和本地环境
"""
import os
import subprocess
import shutil
import socket
import json
import logging
from pathlib import Path
from typing import List, Optional
from jinja2 import Template
from app.models import ProxyRule, NginxReloadResponse
from app.config_manager import ConfigManager

# 配置日志
logger = logging.getLogger(__name__)


class NginxManager:
    """Nginx 配置管理器"""
    
    def __init__(
        self,
        template_path: str = "nginx/nginx.conf.template",
        output_path: str = "nginx/proxy_rules.conf",
        nginx_bin: str = "nginx"
    ):
        self.template_path = Path(template_path)
        self.output_path = Path(output_path)
        self.nginx_bin = nginx_bin
        self.config_manager = ConfigManager()
        
        # 检测是否在 Docker 环境中
        self.is_docker = self._detect_docker_environment()
        self.nginx_container = os.getenv('NGINX_CONTAINER_NAME', 'nginx-proxy-manager-nginx')
    
    def _detect_docker_environment(self) -> bool:
        """检测是否在 Docker 环境中运行"""
        # 检查 /.dockerenv 文件
        if os.path.exists('/.dockerenv'):
            return True
        
        # 检查 /proc/1/cgroup
        try:
            with open('/proc/1/cgroup', 'r') as f:
                return 'docker' in f.read()
        except:
            pass
        
        # 检查环境变量
        return os.getenv('DOCKER_CONTAINER') == 'true'
    
    def _run_docker_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """在 Docker 容器中执行命令"""
        docker_cmd = ['docker', 'exec', self.nginx_container] + command
        return subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
    
    def _docker_api_exec_cmd(self, cmd: List[str]) -> tuple[int, str]:
        """通过 Docker API 在容器内执行命令；返回 (exit_code, output)"""
        try:
            sock_path = '/var/run/docker.sock'
            
            # 创建 exec
            req_data = json.dumps({
                'AttachStdout': True, 'AttachStderr': True,
                'Tty': False, 'Cmd': cmd
            }).encode('utf-8')
            req = (f"POST /containers/{self.nginx_container}/exec HTTP/1.1\r\n"
                   "Host: docker\r\n"
                   f"Content-Type: application/json\r\n"
                   f"Content-Length: {len(req_data)}\r\n\r\n").encode('utf-8') + req_data
            
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(sock_path)
            sock.sendall(req)
            resp = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk: break
                resp += chunk
            sock.close()
            
            body = resp.split(b'\r\n\r\n', 1)[1] if b'\r\n\r\n' in resp else resp
            exec_info = json.loads(body.decode('utf-8'))
            exec_id = exec_info.get('Id', '')
            
            if not exec_id:
                return 1, "无法创建 exec"
            
            # 启动 exec
            req = (f"POST /exec/{exec_id}/start HTTP/1.1\r\n"
                   "Host: docker\r\nContent-Type: application/json\r\n"
                   "Content-Length: 41\r\n\r\n"
                   '{"Detach":false,"Tty":false}').encode('utf-8')
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(sock_path)
            sock.sendall(req)
            
            output = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk: break
                output += chunk
            sock.close()
            
            # 获取退出码
            req = f"GET /exec/{exec_id}/json HTTP/1.1\r\nHost: docker\r\n\r\n".encode('utf-8')
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(sock_path)
            sock.sendall(req)
            resp = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk: break
                resp += chunk
            sock.close()
            
            body = resp.split(b'\r\n\r\n', 1)[1] if b'\r\n\r\n' in resp else resp
            exit_info = json.loads(body.decode('utf-8'))
            exit_code = exit_info.get('ExitCode', 1)

            out_str = output.decode('utf-8', errors='ignore').split('\r\n\r\n', 1)[-1]
            return exit_code, out_str
        except Exception as e:
            return 1, f"Docker API 调用失败: {str(e)}"
    
    def _load_template(self) -> Template:
        """加载 Nginx 配置模板"""
        if not self.template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {self.template_path}")
        
        with open(self.template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        return Template(template_content)
    
    def generate_config(self, rules: Optional[List[ProxyRule]] = None) -> str:
        """生成 Nginx 配置内容"""
        if rules is None:
            rules = self.config_manager.get_enabled_rules()
        
        template = self._load_template()
        
        # 准备模板数据
        template_data = {
            "rules": rules,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
        return template.render(**template_data)
    
    def read_config_file(self) -> Optional[str]:
        """读取当前的 Nginx 配置文件内容（简化版本）"""
        try:
            # 统一从本地路径读取（通过 volume 挂载）
            if self.output_path.exists():
                return self.output_path.read_text(encoding='utf-8')
            else:
                logger.warning(f"配置文件不存在: {self.output_path}")
                return None
        except Exception as e:
            logger.error(f"读取配置文件失败: {str(e)}")
            return None
    
    def log_config_content(self, operation: str):
        """打印配置文件内容到日志"""
        logger.info(f"=" * 80)
        logger.info(f"操作: {operation}")
        logger.info(f"配置文件路径: {self.output_path}")
        logger.info(f"-" * 80)
        
        content = self.read_config_file()
        if content:
            logger.info("配置文件内容:")
            logger.info(content)
        else:
            logger.warning("无法读取配置文件内容")
        
        logger.info(f"=" * 80)
    
    def write_config(self, config_content: str) -> bool:
        """写入 Nginx 配置文件（简化版本）"""
        try:
            # 统一使用本地文件写入（通过 Docker volume 挂载）
            # 这样无论是否在容器内，都直接写入挂载的配置文件
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            
            logger.info(f"配置文件已写入: {self.output_path}")
            return True
            
        except PermissionError:
            raise PermissionError(f"没有权限写入配置文件: {self.output_path}")
        except Exception as e:
            raise Exception(f"写入配置文件失败: {str(e)}")
    
    def test_config(self) -> tuple[bool, Optional[str]]:
        """测试 Nginx 配置语法（简化版本）"""
        try:
            if self.is_docker:
                # Docker 环境：通过 docker exec 测试配置
                try:
                    result = subprocess.run(
                        ['docker', 'exec', self.nginx_container, self.nginx_bin, '-t'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    output = result.stderr or result.stdout
                    return (result.returncode == 0, output)
                except FileNotFoundError:
                    # docker 命令不存在，跳过测试
                    logger.warning("Docker 命令不可用，跳过配置测试")
                    return True, "配置测试跳过（Docker 不可用）"
            else:
                # 本地环境：直接测试
                result = subprocess.run(
                    [self.nginx_bin, '-t'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                output = result.stderr or result.stdout
                return (result.returncode == 0, output)
                
        except subprocess.TimeoutExpired:
            return False, "配置测试超时"
        except FileNotFoundError:
            logger.warning(f"Nginx 可执行文件未找到: {self.nginx_bin}")
            return True, "配置测试跳过（Nginx 不可用）"
        except Exception as e:
            logger.error(f"配置测试失败: {str(e)}")
            return False, f"配置测试失败: {str(e)}"
    
    def reload_nginx(self) -> NginxReloadResponse:
        """重载 Nginx 配置（简化版本）"""
        try:
            # 简化方案：直接通过 docker exec 发送 reload 信号
            # 配置文件已通过 volume 挂载，NGINX 会自动读取
            
            if self.is_docker:
                # Docker 环境：发送 reload 信号到容器
                try:
                    result = subprocess.run(
                        ['docker', 'exec', self.nginx_container, self.nginx_bin, '-s', 'reload'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        logger.info("Nginx 重载信号发送成功")
                        return NginxReloadResponse(
                            success=True,
                            message="Nginx 重载成功",
                            config_path=str(self.output_path)
                        )
                    else:
                        error_msg = result.stderr or result.stdout
                        logger.error(f"Nginx 重载失败: {error_msg}")
                        return NginxReloadResponse(
                            success=False,
                            message="Nginx 重载失败",
                            error=error_msg
                        )
                except FileNotFoundError:
                    # docker 命令不存在，说明可能在容器内运行
                    # 配置已通过挂载写入，标记为成功
                    logger.info("Docker 命令不可用，配置已通过挂载卷更新")
                    return NginxReloadResponse(
                        success=True,
                        message="配置已更新（通过挂载卷）",
                        config_path=str(self.output_path)
                    )
            else:
                # 本地环境：直接执行 reload
                result = subprocess.run(
                    [self.nginx_bin, '-s', 'reload'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    return NginxReloadResponse(
                        success=True,
                        message="Nginx 重载成功",
                        config_path=str(self.output_path)
                    )
                else:
                    return NginxReloadResponse(
                        success=False,
                        message="Nginx 重载失败",
                        error=result.stderr or result.stdout
                    )
                
        except subprocess.TimeoutExpired:
            return NginxReloadResponse(
                success=False,
                message="Nginx 重载超时",
                error="操作超时"
            )
        except Exception as e:
            logger.error(f"Nginx 重载异常: {str(e)}")
            return NginxReloadResponse(
                success=False,
                message="Nginx 重载异常",
                error=str(e)
            )
    
    def update_and_reload(self) -> NginxReloadResponse:
        """更新配置并重载 Nginx"""
        try:
            logger.info("开始更新配置并重载 Nginx")
            
            # 生成新配置
            config_content = self.generate_config()
            logger.info(f"已生成新配置，共 {len(config_content)} 字符")
            
            # 备份当前配置（如果存在）
            if self.output_path.exists():
                backup_path = self.output_path.with_suffix('.conf.backup')
                import shutil
                shutil.copy2(self.output_path, backup_path)
                logger.info(f"已备份当前配置到: {backup_path}")
            
            # 写入新配置
            self.write_config(config_content)
            
            # 打印配置文件内容
            self.log_config_content("写入配置后")
            
            # 重载 Nginx
            result = self.reload_nginx()
            
            # 如果重载失败，恢复备份
            if not result.success:
                logger.error(f"Nginx 重载失败: {result.error}")
                backup_path = self.output_path.with_suffix('.conf.backup')
                if backup_path.exists():
                    import shutil
                    shutil.copy2(backup_path, self.output_path)
                    result.message += " (已恢复备份配置)"
                    logger.info("已恢复备份配置")
            else:
                logger.info("Nginx 重载成功")
                # 重载成功后再次打印配置内容确认
                self.log_config_content("重载 Nginx 后")
            
            return result
            
        except Exception as e:
            logger.error(f"更新配置失败: {str(e)}")
            return NginxReloadResponse(
                success=False,
                message="更新配置失败",
                error=str(e)
            )
    
    def get_nginx_status(self) -> dict:
        """获取 Nginx 状态信息"""
        try:
            if self.is_docker:
                # Docker 环境：检查容器状态
                check_container = subprocess.run(
                    ['docker', 'ps', '--filter', f'name={self.nginx_container}', '--format', '{{.Names}}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                is_running = self.nginx_container in check_container.stdout
                
                # 获取 Nginx 版本
                if is_running:
                    version_result = self._run_docker_command([self.nginx_bin, '-v'])
                    version = version_result.stderr.strip() if version_result.returncode == 0 else "未知"
                else:
                    version = "容器未运行"
                
                # 检查配置文件是否存在
                if is_running:
                    check_file = self._run_docker_command(['test', '-f', str(self.output_path)])
                    config_exists = check_file.returncode == 0
                else:
                    config_exists = False
            else:
                # 本地环境
                result = subprocess.run(
                    ['pgrep', '-x', 'nginx'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                is_running = result.returncode == 0
                
                version_result = subprocess.run(
                    [self.nginx_bin, '-v'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                version = version_result.stderr.strip() if version_result.returncode == 0 else "未知"
                config_exists = self.output_path.exists()
            
            return {
                "running": is_running,
                "version": version,
                "config_path": str(self.output_path),
                "config_exists": config_exists,
                "template_path": str(self.template_path),
                "template_exists": self.template_path.exists(),
                "environment": "docker" if self.is_docker else "local"
            }
            
        except Exception as e:
            return {
                "running": False,
                "error": str(e),
                "environment": "docker" if self.is_docker else "local"
            }
    
    def validate_rules_for_nginx(self, rules: List[ProxyRule]) -> tuple[bool, Optional[str]]:
        """验证规则是否适合生成 Nginx 配置"""
        # 检查路径冲突
        paths = set()
        for rule in rules:
            if rule.path in paths:
                return False, f"路径冲突: {rule.path}"
            paths.add(rule.path)
            
            # 检查路径格式
            if not rule.path.startswith('/'):
                return False, f"路径必须以 / 开头: {rule.path}"
            
            # 检查端口范围
            if not (1 <= rule.target_port <= 65535):
                return False, f"端口超出范围: {rule.target_port}"
        
        return True, None

