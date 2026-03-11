"""
网页内容抓取工具

给定 URL，抓取网页正文内容供 AI 阅读分析。
"""
from typing import Dict, Any
from ..base import Tool, RiskLevel, ToolParameter


class WebFetchTool(Tool):
    """抓取指定 URL 的网页正文内容"""

    name = "web_fetch"
    description = "抓取指定网页的正文内容。通常在 web_search 之后使用，用于精读某个网页的详细信息。"
    category = "web"
    risk_level = RiskLevel.SAFE

    parameters = {
        "url": ToolParameter(
            type="string",
            description="要抓取的网页 URL"
        ),
        "max_length": ToolParameter(
            type="integer",
            description="返回内容的最大字符数，默认 8000"
        )
    }
    required_params = ["url"]

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        抓取网页正文

        Args:
            url: 目标网页地址
            max_length: 最大字符数，默认 8000

        Returns:
            {
                "success": True,
                "data": {
                    "url": "...",
                    "title": "...",
                    "content": "...",   # 提取的正文
                    "length": 1234
                }
            }
        """
        try:
            import httpx
        except ImportError:
            return {
                "success": False,
                "error": "缺少依赖：请运行 pip install httpx"
            }

        url = kwargs.get("url")
        max_length = kwargs.get("max_length", 8000)

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }

            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=15.0
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                # 非 HTML 内容（如 PDF、JSON）直接截断返回
                text = response.text[:max_length]
                return {
                    "success": True,
                    "data": {
                        "url": url,
                        "title": "",
                        "content": text,
                        "length": len(text)
                    }
                }

            # 提取正文
            title, content = self._extract_content(response.text)
            content = content[:max_length]

            return {
                "success": True,
                "data": {
                    "url": url,
                    "title": title,
                    "content": content,
                    "length": len(content)
                }
            }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP 错误 {e.response.status_code}: {url}"
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": f"请求超时: {url}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _extract_content(self, html: str) -> tuple[str, str]:
        """
        从 HTML 提取标题和正文

        优先使用 readability-lxml，降级到 BeautifulSoup 简单提取
        """
        # 尝试 readability（效果最好）
        try:
            from readability import Document
            doc = Document(html)
            title = doc.title()
            # readability 返回 HTML，再用 BS4 转纯文本
            content_html = doc.summary()
            return title, self._html_to_text(content_html)
        except ImportError:
            pass

        # 降级：BeautifulSoup 基础提取
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # 标题
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # 移除噪音标签
            for tag in soup(["script", "style", "nav", "header", "footer",
                             "aside", "iframe", "noscript"]):
                tag.decompose()

            # 取正文
            content = soup.get_text(separator="\n", strip=True)
            # 合并连续空行
            lines = [line for line in content.splitlines() if line.strip()]
            return title, "\n".join(lines)
        except ImportError:
            pass

        # 最后兜底：直接去除 HTML 标签
        import re
        title = ""
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
        content = re.sub(r"<[^>]+>", " ", html)
        content = re.sub(r"\s+", " ", content).strip()
        return title, content

    def _html_to_text(self, html: str) -> str:
        """将 HTML 片段转为纯文本"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            lines = [line for line in soup.get_text(separator="\n", strip=True).splitlines() if line.strip()]
            return "\n".join(lines)
        except ImportError:
            import re
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
