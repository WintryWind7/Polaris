# Polaris 日志系统使用指南

## 功能特性

✅ **自动去除 backend. 前缀** - 显示 `[core.memory]` 而不是 `[backend.core.memory]`
✅ **按日期自动轮转** - 每天午夜自动创建新日志文件，保留 30 天
✅ **双输出** - 同时输出到控制台和文件
✅ **彩色控制台** - 开发模式下不同级别用不同颜色显示
✅ **详细的文件日志** - 包含函数名和行号，方便定位问题
✅ **异常堆栈追踪** - 自动记录完整的异常信息

## 快速开始

### 1. 在模块中使用

```python
from backend.logger import get_logger

# 在模块顶部创建 logger（使用 __name__ 自动获取模块名）
logger = get_logger(__name__)

# 使用日志
logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")

# 记录异常（自动包含堆栈）
try:
    risky_operation()
except Exception as e:
    logger.exception("操作失败")  # 推荐
    # 或者
    logger.error("操作失败", exc_info=True)
```

### 2. 初始化日志系统

在应用启动时调用一次（已在 `server.py` 中配置）：

```python
from backend.logger import setup_logging

setup_logging(
    level="INFO",           # 日志级别: DEBUG/INFO/WARNING/ERROR/CRITICAL
    enable_console=True,    # 是否输出到控制台
    enable_file=True,       # 是否输出到文件
    enable_color=True       # 是否启用控制台颜色（开发模式）
)
```

## 日志级别说明

| 级别 | 用途 | 示例 |
|------|------|------|
| `DEBUG` | 详细的调试信息 | `logger.debug(f"变量值: x={x}, y={y}")` |
| `INFO` | 正常操作记录 | `logger.info("用户登录成功")` |
| `WARNING` | 警告但不影响运行 | `logger.warning("配置项缺失，使用默认值")` |
| `ERROR` | 错误但程序可继续 | `logger.error("API 调用失败")` |
| `CRITICAL` | 严重错误，程序可能崩溃 | `logger.critical("数据库连接断开")` |

## 日志格式

### 控制台输出（简洁）
```
[2026-03-04 23:31:15][core.memory][INFO] 添加对话记录: user=你好...
```

### 文件输出（详细）
```
[2026-03-04 23:31:15][core.memory][INFO][add_chat:115] 添加对话记录: user=你好...
```

## 日志文件位置

- **路径**: `data/logs/polaris.log`
- **轮转**: 每天午夜自动创建新文件（如 `polaris.log.2026-03-05`）
- **保留**: 最近 30 天的日志

## 环境变量

可以通过环境变量控制日志级别：

```bash
# Windows PowerShell
$env:POLARIS_LOG_LEVEL="DEBUG"
python main.py

# Linux/Mac
export POLARIS_LOG_LEVEL=DEBUG
python main.py
```

## 最佳实践

### ✅ 推荐做法

```python
# 1. 使用 f-string 格式化
logger.info(f"处理请求: user_id={user_id}, action={action}")

# 2. 记录关键操作
logger.info("开始处理任务")
result = process_task()
logger.info(f"任务完成: result={result}")

# 3. 异常时使用 exception()
try:
    dangerous_operation()
except Exception as e:
    logger.exception("操作失败")  # 自动包含堆栈
    raise

# 4. 敏感信息脱敏
logger.info(f"API Key: {api_key[:8]}...")  # 只显示前 8 位
```

### ❌ 避免做法

```python
# 1. 不要在循环中打印大量日志
for item in items:
    logger.debug(f"处理 {item}")  # 如果 items 很多会刷屏

# 2. 不要记录敏感信息
logger.info(f"密码: {password}")  # 危险！

# 3. 不要使用 print()
print("这不会被记录到日志文件")  # 应该用 logger.info()
```

## 模块名示例

使用 `__name__` 会自动生成正确的模块名：

| 文件路径 | `__name__` | 日志中显示 |
|----------|-----------|-----------|
| `backend/core/memory.py` | `backend.core.memory` | `[core.memory]` |
| `backend/agents/main_agent.py` | `backend.agents.main_agent` | `[agents.main_agent]` |
| `backend/api/server.py` | `backend.api.server` | `[api.server]` |

## 查看日志

### 实时查看（开发时）
```bash
# Windows PowerShell
Get-Content data/logs/polaris.log -Wait -Tail 50

# Linux/Mac
tail -f data/logs/polaris.log
```

### 过滤特定模块
```bash
# 只看 core.llm 模块的日志
grep "\[core.llm\]" data/logs/polaris.log

# 只看错误日志
grep "\[ERROR\]" data/logs/polaris.log
```

## 前端日志（待实现）

前端日志系统将在后续版本中添加，计划功能：
- 封装 `console.log/warn/error`
- 支持按模块过滤
- 错误自动上报到后端
- 与后端日志统一格式

## 故障排查

### 问题：日志文件没有生成

**解决**：检查 `data/logs/` 目录权限，确保程序有写入权限。

### 问题：控制台中文乱码

**解决**：这是 Windows 终端编码问题，不影响日志文件。日志文件中的中文是正常的。

### 问题：日志太多影响性能

**解决**：
1. 生产环境设置 `level="INFO"` 或 `"WARNING"`
2. 减少 DEBUG 级别的日志
3. 避免在高频循环中打印日志

## 示例代码

完整示例请参考 `backend/logger/example.py`。
