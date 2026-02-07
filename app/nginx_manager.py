"""
Nginx 配置管理模块
负责生成 Nginx 配置文件并重载 Nginx
支持 Docker 环境和本地环境
"""
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional
from jinja2 import Template
from app.models import ProxyRule, NginxReloadResponse
from app.config_manager import ConfigManager


class NginxManager:
    """Nginx 配置管理器"""
    
    def __init__(
        self,
        template_path: str = "nginx/nginx.conf.template",
        output_path: str = "/etc/nginx/conf.d/proxy_rules.conf",
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
    
    def write_config(self, config_content: str) -> bool:
        """写入 Nginx 配置文件"""
        try:
            if self.is_docker:
                # Docker 环境：优先通过 docker exec 写入文件
                # 如果容器内没有 docker CLI（例如镜像未安装 docker 客户端），
                # 尝试回退到写入主机挂载的配置文件（如果存在）
                if shutil.which('docker') is None:
                    # 常见的主机挂载路径候选（容器内相对路径）
                    candidate_paths = [Path('/app/nginx/proxy_rules.conf'), Path('nginx/proxy_rules.conf')]
                    for p in candidate_paths:
                        try:
                            if p.exists():
                                p.write_text(config_content, encoding='utf-8')
                                return True
                        except Exception:
                            continue

                    raise FileNotFoundError("docker CLI 未找到，且未检测到可写的主机挂载配置文件")

                # 使用 docker exec 写入到 nginx 容器
                write_cmd = ['sh', '-c', f'cat > {self.output_path}']
                result = subprocess.run(
                    ['docker', 'exec', '-i', self.nginx_container] + write_cmd,
                    input=config_content,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    raise Exception(f"Docker 写入失败: {result.stderr}")

                return True
            else:
                # 本地环境：直接写入文件
                self.output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(self.output_path, 'w', encoding='utf-8') as f:
                    f.write(config_content)
                
                return True
        except PermissionError:
            raise PermissionError(f"没有权限写入配置文件: {self.output_path}")
        except Exception as e:
            raise Exception(f"写入配置文件失败: {str(e)}")
    
    def test_config(self) -> tuple[bool, Optional[str]]:
        """测试 Nginx 配置语法"""
        try:
            if self.is_docker:
                # Docker 环境：通过 docker exec 执行
                result = self._run_docker_command([self.nginx_bin, '-t'])
            else:
                # 本地环境：直接执行
                result = subprocess.run(
                    [self.nginx_bin, '-t'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            # nginx -t 的输出在 stderr 中
            output = result.stderr
            
            if result.returncode == 0:
                return True, output
            else:
                return False, output
                
        except subprocess.TimeoutExpired:
            return False, "配置测试超时"
        except FileNotFoundError:
            return False, f"Nginx 可执行文件未找到: {self.nginx_bin}"
        except Exception as e:
            return False, f"配置测试失败: {str(e)}"
    
    def reload_nginx(self) -> NginxReloadResponse:
        """重载 Nginx 配置"""
        try:
            # 先测试配置
            is_valid, test_output = self.test_config()
            
            if not is_valid:
                return NginxReloadResponse(
                    success=False,
                    message="Nginx 配置测试失败",
                    error=test_output
                )
            
            # 重载 Nginx
            if self.is_docker:
                # Docker 环境：通过 docker exec 执行
                result = self._run_docker_command([self.nginx_bin, '-s', 'reload'])
            else:
                # 本地环境：直接执行
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
            return NginxReloadResponse(
                success=False,
                message="Nginx 重载异常",
                error=str(e)
            )
    
    def update_and_reload(self) -> NginxReloadResponse:
        """更新配置并重载 Nginx"""
        try:
            # 生成新配置
            config_content = self.generate_config()
            
            # 备份当前配置（如果存在）
            if self.output_path.exists():
                backup_path = self.output_path.with_suffix('.conf.backup')
                import shutil
                shutil.copy2(self.output_path, backup_path)
            
            # 写入新配置
            self.write_config(config_content)
            
            # 重载 Nginx
            result = self.reload_nginx()
            
            # 如果重载失败，恢复备份
            if not result.success:
                backup_path = self.output_path.with_suffix('.conf.backup')
                if backup_path.exists():
                    import shutil
                    shutil.copy2(backup_path, self.output_path)
                    result.message += " (已恢复备份配置)"
            
            return result
            
        except Exception as e:
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
