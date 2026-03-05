"""
日志系统使用示例

演示如何在各个模块中使用日志系统。
"""
from backend.logger import get_logger

# 在模块顶部创建 logger
logger = get_logger(__name__)


def example_function():
    """示例函数"""
    # 不同级别的日志
    logger.debug("这是调试信息 - 仅在 DEBUG 级别显示")
    logger.info("这是普通信息 - 正常操作记录")
    logger.warning("这是警告信息 - 需要注意但不影响运行")
    logger.error("这是错误信息 - 发生了错误")

    # 记录异常（自动包含堆栈信息）
    try:
        result = 1 / 0
    except Exception as e:
        logger.exception("发生异常")  # 等同于 logger.error(..., exc_info=True)

    # 带变量的日志
    user_id = 12345
    action = "登录"
    logger.info(f"用户操作: user_id={user_id}, action={action}")


if __name__ == "__main__":
    from backend.logger import setup_logging

    # 初始化日志系统
    setup_logging(
        level="DEBUG",
        enable_console=True,
        enable_file=True,
        enable_color=True
    )

    # 运行示例
    logger.info("=" * 50)
    logger.info("日志系统测试开始")
    logger.info("=" * 50)

    example_function()

    logger.info("=" * 50)
    logger.info("日志系统测试结束")
    logger.info("=" * 50)
