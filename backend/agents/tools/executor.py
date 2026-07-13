"""
工具执行器

处理 Function Calling 循环，执行工具并构建响应。
支持 readFileState：确保 write_file 前必须先 read_file。
"""
import json
from typing import Dict, Any, Optional
from .registry import ToolRegistry
from ...logger import get_logger

logger = get_logger(__name__)


class ToolExecutor:
    """工具执行器（处理 function calling 循环）"""

    def __init__(self, registry: ToolRegistry, read_file_state=None):
        """
        初始化工具执行器

        Args:
            registry: 工具注册表
            read_file_state: 可选的 ReadFileState 实例，用于强制执行"先读后写"
        """
        self.registry = registry
        self._read_file_state = read_file_state

    async def execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个 tool_call

        Args:
            tool_call: {
                "id": "call_xxx",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "/tmp/test.txt"}'
                }
            }

        Returns:
            {
                "role": "tool",
                "tool_call_id": "call_xxx",
                "name": "read_file",
                "content": "{\"success\": true, \"data\": \"...\"}"
            }
        """
        tool_call_id = tool_call["id"]
        function_name = tool_call["function"]["name"]
        arguments_str = tool_call["function"]["arguments"]

        try:
            # 1. 解析参数
            arguments = json.loads(arguments_str)
            logger.debug(f"执行工具: {function_name}, 参数: {arguments}")

            # 2. 获取工具
            tool = self.registry.get(function_name)
            if not tool:
                return self._error_response(
                    tool_call_id, function_name, f"工具不存在: {function_name}"
                )

            # 3. 参数校验
            if not tool.validate_params(**arguments):
                return self._error_response(
                    tool_call_id, function_name, "参数校验失败"
                )

            # 4. readFileState 检查：write_file 前必须读过文件（新文件豁免）
            if self._read_file_state and function_name == "write_file":
                path = arguments.get("path", "")
                if path:
                    allowed, reason = self._read_file_state.can_write(path)
                    if not allowed:
                        logger.warning(f"write_file 被拒绝: {path} — {reason}")
                        return self._error_response(
                            tool_call_id, function_name, reason
                        )

            # 5. 执行工具
            result = await tool.execute(**arguments)

            # 6. readFileState 登记
            if self._read_file_state and result.get("success"):
                if function_name == "read_file":
                    path = arguments.get("path", "")
                    content = result.get("content", "")
                    if path and content:
                        self._read_file_state.register(path, content)
                        logger.debug(f"readFileState 登记读取: {path}")
                elif function_name == "write_file":
                    path = arguments.get("path", "")
                    content = arguments.get("content", "")
                    if path and content:
                        self._read_file_state.register(path, content)
                        logger.debug(f"readFileState 续期写入: {path}")

            # 7. 返回结果
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": function_name,
                "content": json.dumps(result, ensure_ascii=False)
            }

        except json.JSONDecodeError as e:
            logger.error(f"参数解析失败: {e}")
            return self._error_response(
                tool_call_id, function_name, f"参数格式错误: {e}"
            )

        except Exception as e:
            logger.error(f"工具执行失败: {e}", exc_info=True)
            return self._error_response(
                tool_call_id, function_name, f"执行失败: {str(e)}"
            )

    def _error_response(
        self, tool_call_id: str, name: str, error: str
    ) -> Dict[str, Any]:
        """
        构建错误响应

        Args:
            tool_call_id: 工具调用 ID
            name: 工具名称
            error: 错误信息

        Returns:
            错误响应字典
        """
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": json.dumps(
                {"success": False, "error": error}, ensure_ascii=False
            )
        }
