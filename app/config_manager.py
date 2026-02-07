"""
配置文件管理模块
负责读取、写入和管理 YAML 配置文件
"""
import os
import yaml
import shutil
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from app.models import ProxyRule


class ConfigManager:
    """配置文件管理器"""
    
    def __init__(self, config_path: str = "config/proxy_config.yaml"):
        self.config_path = Path(config_path)
        self.backup_dir = self.config_path.parent / "backups"
        self._ensure_config_exists()
        self._ensure_backup_dir()
    
    def _ensure_config_exists(self):
        """确保配置文件存在，如果不存在则创建默认配置"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.config_path.exists():
            default_config = {
                "rules": []
            }
            self._write_yaml(default_config)
    
    def _ensure_backup_dir(self):
        """确保备份目录存在"""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _read_yaml(self) -> dict:
        """读取 YAML 配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config if config else {"rules": []}
        except Exception as e:
            raise Exception(f"读取配置文件失败: {str(e)}")
    
    def _write_yaml(self, config: dict):
        """写入 YAML 配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise Exception(f"写入配置文件失败: {str(e)}")
    
    def _backup_config(self):
        """备份当前配置文件"""
        if self.config_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"proxy_config_{timestamp}.yaml"
            shutil.copy2(self.config_path, backup_path)
            
            # 只保留最近10个备份
            backups = sorted(self.backup_dir.glob("proxy_config_*.yaml"))
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    old_backup.unlink()
    
    def get_all_rules(self) -> List[ProxyRule]:
        """获取所有代理规则"""
        config = self._read_yaml()
        rules = []
        
        for idx, rule_data in enumerate(config.get("rules", [])):
            rule_data["id"] = rule_data.get("id", str(idx))
            rules.append(ProxyRule(**rule_data))
        
        return rules
    
    def get_rule_by_id(self, rule_id: str) -> Optional[ProxyRule]:
        """根据ID获取代理规则"""
        rules = self.get_all_rules()
        for rule in rules:
            if rule.id == rule_id:
                return rule
        return None
    
    def get_rule_by_path(self, path: str) -> Optional[ProxyRule]:
        """根据路径获取代理规则"""
        rules = self.get_all_rules()
        for rule in rules:
            if rule.path == path:
                return rule
        return None
    
    def add_rule(self, rule: ProxyRule) -> ProxyRule:
        """添加新的代理规则"""
        # 备份当前配置
        self._backup_config()
        
        # 读取当前配置
        config = self._read_yaml()
        rules = config.get("rules", [])
        
        # 检查路径是否已存在
        for existing_rule in rules:
            if existing_rule.get("path") == rule.path:
                raise ValueError(f"路径 {rule.path} 已存在")
        
        # 生成新ID
        if rule.id is None:
            existing_ids = [int(r.get("id", 0)) for r in rules if r.get("id", "").isdigit()]
            rule.id = str(max(existing_ids, default=0) + 1)
        
        # 设置时间戳
        now = datetime.now()
        rule.created_at = now
        rule.updated_at = now
        
        # 添加规则
        rule_dict = rule.model_dump(exclude_none=True)
        rule_dict["created_at"] = rule.created_at.isoformat()
        rule_dict["updated_at"] = rule.updated_at.isoformat()
        rules.append(rule_dict)
        
        # 保存配置
        config["rules"] = rules
        self._write_yaml(config)
        
        return rule
    
    def update_rule(self, rule_id: str, updates: dict) -> ProxyRule:
        """更新代理规则"""
        # 备份当前配置
        self._backup_config()
        
        # 读取当前配置
        config = self._read_yaml()
        rules = config.get("rules", [])
        
        # 查找并更新规则
        rule_found = False
        for idx, rule in enumerate(rules):
            if rule.get("id") == rule_id:
                # 如果更新路径，检查新路径是否已存在
                if "path" in updates and updates["path"] != rule.get("path"):
                    for other_rule in rules:
                        if other_rule.get("id") != rule_id and other_rule.get("path") == updates["path"]:
                            raise ValueError(f"路径 {updates['path']} 已存在")
                
                # 更新字段
                for key, value in updates.items():
                    if value is not None:
                        rule[key] = value
                
                # 更新时间戳
                rule["updated_at"] = datetime.now().isoformat()
                rules[idx] = rule
                rule_found = True
                break
        
        if not rule_found:
            raise ValueError(f"规则 ID {rule_id} 不存在")
        
        # 保存配置
        config["rules"] = rules
        self._write_yaml(config)
        
        # 返回更新后的规则
        return ProxyRule(**rules[idx])
    
    def delete_rule(self, rule_id: str) -> bool:
        """删除代理规则"""
        # 备份当前配置
        self._backup_config()
        
        # 读取当前配置
        config = self._read_yaml()
        rules = config.get("rules", [])
        
        # 查找并删除规则
        initial_count = len(rules)
        rules = [rule for rule in rules if rule.get("id") != rule_id]
        
        if len(rules) == initial_count:
            raise ValueError(f"规则 ID {rule_id} 不存在")
        
        # 保存配置
        config["rules"] = rules
        self._write_yaml(config)
        
        return True
    
    def validate_config(self) -> tuple[bool, Optional[str]]:
        """验证配置文件的有效性"""
        try:
            config = self._read_yaml()
            
            if not isinstance(config, dict):
                return False, "配置文件格式错误：根节点必须是字典"
            
            if "rules" not in config:
                return False, "配置文件缺少 rules 字段"
            
            if not isinstance(config["rules"], list):
                return False, "rules 字段必须是列表"
            
            # 验证每个规则
            paths = set()
            for idx, rule in enumerate(config["rules"]):
                try:
                    ProxyRule(**rule)
                except Exception as e:
                    return False, f"规则 {idx} 验证失败: {str(e)}"
                
                # 检查路径重复
                path = rule.get("path")
                if path in paths:
                    return False, f"路径 {path} 重复"
                paths.add(path)
            
            return True, None
            
        except Exception as e:
            return False, f"配置验证失败: {str(e)}"
    
    def get_enabled_rules(self) -> List[ProxyRule]:
        """获取所有启用的代理规则"""
        all_rules = self.get_all_rules()
        return [rule for rule in all_rules if rule.enabled]
    
    def restore_from_backup(self, backup_filename: str) -> bool:
        """从备份恢复配置"""
        backup_path = self.backup_dir / backup_filename
        
        if not backup_path.exists():
            raise FileNotFoundError(f"备份文件 {backup_filename} 不存在")
        
        # 备份当前配置
        self._backup_config()
        
        # 恢复备份
        shutil.copy2(backup_path, self.config_path)
        
        # 验证恢复后的配置
        is_valid, error = self.validate_config()
        if not is_valid:
            raise ValueError(f"恢复的配置文件无效: {error}")
        
        return True
    
    def list_backups(self) -> List[dict]:
        """列出所有备份文件"""
        backups = []
        for backup_file in sorted(self.backup_dir.glob("proxy_config_*.yaml"), reverse=True):
            backups.append({
                "filename": backup_file.name,
                "created_at": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat(),
                "size": backup_file.stat().st_size
            })
        return backups
