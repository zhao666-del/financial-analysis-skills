# -*- coding: utf-8 -*-
"""配置管理 — 加载 config.yaml (用户) + config/default.yaml (默认)"""

import os
import yaml
from typing import Dict


_config_cache = None


def load_config() -> Dict:
    """加载配置: config.yaml 覆盖 config/default.yaml
    
    优先级: config/config.yaml > config/default.yaml
    
    Returns:
        dict: 合并后的配置
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    
    config_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(config_dir)
    
    # 默认配置
    default_path = os.path.join(config_dir, "default.yaml")
    default_cfg = {}
    if os.path.exists(default_path):
        with open(default_path, "r", encoding="utf-8") as f:
            default_cfg = yaml.safe_load(f) or {}
    
    # 用户配置
    user_path = os.path.join(config_dir, "config.yaml")
    user_cfg = {}
    if os.path.exists(user_path):
        with open(user_path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
    
    # 合并 (用户覆盖默认)
    _config_cache = {**default_cfg, **user_cfg}
    return _config_cache


def get_proxy() -> str:
    """获取 HTTPS 代理地址
    
    优先级: HTTPS_PROXY 环境变量 > config.yaml proxy.https
    
    Returns:
        str: 代理地址，如 "http://127.0.0.1:10809"，无代理返回空字符串
    """
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy", "")
    if proxy:
        return proxy
    
    cfg = load_config()
    return cfg.get("proxy", {}).get("https", "")
