"""
子 Agent 测试脚本

直接测试子 Agent，跳过主 Agent 调度。
模型从 providers.json 配置读取，不硬编码。

用法:
  python scripts/test_subagent.py coding "读取 backend/agents/base.py 的前 10 行"
  python scripts/test_subagent.py coding "列出 backend/agents/tools/ 目录结构"
"""
import sys
import asyncio
import time
from pathlib import Path

# 确保项目根目录在 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_subagent_registry():
    """从代码中发现所有已注册的子 Agent"""
    from backend.agents.subagents.coding_agent import CodingAgent
    from backend.agents.subagents.skill_learner import SkillLearnerAgent

    return {
        "coding": CodingAgent,
        "skill_learner": SkillLearnerAgent,
    }


async def run_test(agent_type: str, task: str):
    registry = get_subagent_registry()

    if agent_type not in registry:
        print(f"未知子 Agent: {agent_type}")
        print(f"可用: {', '.join(registry.keys())}")
        return

    # 打印配置信息
    from backend.config.settings import get_settings
    settings = get_settings()
    print(f"模型: {settings.default_model}")
    print(f"API:  {settings.api_base}")
    print(f"Agent: {agent_type}")
    print(f"任务: {task}")
    print("-" * 40)

    agent = registry[agent_type]()
    start = time.time()

    result = await agent.execute({"task": task})

    elapsed = time.time() - start
    print(f"耗时: {elapsed:.1f}s")
    print("-" * 40)
    print(result.get("response", result))


def main():
    if len(sys.argv) < 3:
        print("用法: python scripts/test_subagent.py <agent_type> <task>")
        print()
        registry = get_subagent_registry()
        print(f"可用子 Agent: {', '.join(registry.keys())}")
        sys.exit(1)

    agent_type = sys.argv[1]
    task = sys.argv[2]

    asyncio.run(run_test(agent_type, task))


if __name__ == "__main__":
    main()
