"""
重建 Embedding 索引脚本

用于：
1. 首次启用 embedding 功能
2. 切换 embedding 模型
3. 修复损坏的 embedding 数据
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.core.vector_search import VectorSearchService
from backend.core.embedding import get_embedding_service
from backend.config.settings import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)


def main():
    """重建 embedding 索引"""
    print("=" * 60)
    print("重建 Embedding 索引")
    print("=" * 60)

    try:
        # 1. 获取配置
        settings = get_settings()
        db_path = settings.data_dir / "conversations.db"

        if not db_path.exists():
            print(f"❌ 数据库不存在: {db_path}")
            return 1

        # 2. 初始化服务
        print("\n[1/4] 初始化 Embedding 服务...")
        embedding_service = get_embedding_service()
        model_info = embedding_service.get_model_info()
        print(f"  模型: {model_info['model_name']}")
        print(f"  维度: {model_info['dimension']}")

        # 3. 初始化向量检索服务
        print("\n[2/4] 初始化向量检索服务...")
        vector_search = VectorSearchService(db_path)

        # 显示当前状态
        stats = vector_search.get_stats()
        print(f"  总消息数: {stats['total_messages']}")
        print(f"  应有 embedding: {stats['should_have_embeddings']}")
        print(f"  现有 embedding: {stats['total_embeddings']}")
        print(f"  缺失 embedding: {stats['missing_embeddings']}")

        # 4. 确认操作
        print("\n[3/4] 准备重建...")
        print("  ⚠️  警告：此操作将删除所有现有 embedding 并重新生成")
        response = input("  是否继续？(yes/no): ").strip().lower()

        if response not in ["yes", "y"]:
            print("  已取消")
            return 0

        # 5. 重建
        print("\n[4/4] 重建中...")

        def encode_func(text: str) -> list:
            """编码函数（传递给 vector_search）"""
            return embedding_service.encode(text)

        result = vector_search.rebuild_all(encode_func, batch_size=100)

        # 6. 保存模型信息
        vector_search.set_metadata("model_provider", model_info["provider"])
        vector_search.set_metadata("model_name", model_info["model_name"])
        vector_search.set_metadata("dimension", str(model_info["dimension"]))

        # 7. 显示结果
        print("\n" + "=" * 60)
        print("重建完成")
        print("=" * 60)
        print(f"  总计: {result['total']}")
        print(f"  成功: {result['success']}")
        print(f"  失败: {result['failed']}")

        if result["failed"] > 0:
            print(f"\n  ⚠️  有 {result['failed']} 条消息生成失败，请检查日志")
            return 1

        print("\n✅ 所有 embedding 已成功生成")
        return 0

    except Exception as e:
        logger.error(f"重建失败: {e}", exc_info=True)
        print(f"\n❌ 重建失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
