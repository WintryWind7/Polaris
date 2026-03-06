"""
配置数据模型

使用 Pydantic 定义配置结构，提供类型验证和默认值。
"""
from typing import Optional
from pydantic import BaseModel, Field


# ===== Provider 管理相关模型（用于 providers.json）=====

class ModelConfig(BaseModel):
    """模型配置"""
    model_id: str  # 实际调用的模型 ID
    display_name: str  # 显示名称


class ProviderConfig(BaseModel):
    """LLM 提供商配置（用于 providers.json）"""
    provider_id: str  # 提供商 ID（唯一标识，也是显示名称）
    api_key: str = ""
    api_base_url: str = ""
    models: list[ModelConfig] = Field(default_factory=list)  # 模型列表


# ===== 配置模型（用于 config.json）=====

class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = "127.0.0.1"
    port: int = Field(default=6547, ge=1, le=65535)
    frontend_port: int = Field(default=6546, ge=1, le=65535)
    
    # 记录上一次成功启动的端口，用于迁移清理（代替 .lock 文件）
    last_port: Optional[int] = None
    last_frontend_port: Optional[int] = None


class AgentConfig(BaseModel):
    """Agent 配置"""
    system_prompt: str = "你是 Polaris，一个智能助手。\n你的职责是帮助用户完成各种任务，提供有用、准确、友好的回复。"


class AppConfig(BaseModel):
    """应用配置根模型"""
    server: ServerConfig
    agent: AgentConfig = Field(default_factory=AgentConfig)
