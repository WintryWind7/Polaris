"""
网页搜索工具

使用 DuckDuckGo 搜索互联网，无需 API Key，返回相关结果列表。
"""
from typing import Dict, Any
from ..base import Tool, RiskLevel, ToolParameter


class WebSearchTool(Tool):
    """搜索互联网，获取相关网页列表"""

    name = "web_search"
    description = "搜索互联网获取最新信息。返回相关网页的标题、链接和摘要。适合查询最新资讯、事实核对、不确定的知识。"
    category = "web"
    risk_level = RiskLevel.SAFE

    parameters = {
        "query": ToolParameter(
            type="string",
            description="搜索关键词或问题"
        ),
        "num_results": ToolParameter(
            type="integer",
            description="返回结果数量，默认 5，最多 10"
        ),
        "region": ToolParameter(
            type="string",
            description="搜索地区，如 cn-zh（中国）、us-en（美国），默认 cn-zh"
        )
    }
    required_params = ["query"]

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行网页搜索

        Args:
            query: 搜索关键词
            num_results: 返回数量，默认 5
            region: 地区，默认 cn-zh

        Returns:
            {
                "success": True,
                "data": [
                    {
                        "title": "...",
                        "url": "...",
                        "content": "..."   # 摘要
                    }
                ],
                "query": "..."
            }
        """
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return {
                "success": False,
                "error": "缺少依赖：请运行 pip install duckduckgo-search"
            }

        query = kwargs.get("query")
        num_results = min(kwargs.get("num_results", 5), 10)
        region = kwargs.get("region", "cn-zh")

        try:
            # DDGS 是同步库，在线程池中运行避免阻塞事件循环
            # 国内 Bing 后端容易 302 重定向，优先用 lite，失败则降级到 html
            import asyncio

            def _search():
                for backend in ("lite", "html", "api"):
                    try:
                        results = list(DDGS().text(
                            query,
                            region=region,
                            max_results=num_results,
                            backend=backend
                        ))
                        if results:
                            return results
                    except Exception:
                        continue
                return []

            results = await asyncio.get_event_loop().run_in_executor(None, _search)

            formatted = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "content": r.get("body", "")
                }
                for r in results
            ]

            return {
                "success": True,
                "data": formatted,
                "query": query
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
