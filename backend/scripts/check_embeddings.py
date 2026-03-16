"""
检查 Embedding 一致性脚本

用于：
1. 检查当前配置的模型和数据库中的模型是否一致
2. 显示 embedding 统计信息
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.core.vector_search import VectorSearchService
from backend.core.embedding import get_embedding_service
from backend.config.settings import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)


def main():
    """检查 embedding 一致性"""
    print("=" * 60)
    print("Embedding 一致性检查")
    print("=" * 60)

    try:
        # 1. 获取配置
        settings = get_settings()
        db_path = settings.data_dir / "conversations.db"

        if not db_path.exists():
            print(f"❌ 数据库不存在: {db_path}")
            return 1

        # 2. 获取当前配置的模型
        print("\n[当前配置]")
        embedding_service = get_embedding_service()
        current_model = embedding_service.get_model_info()
        print(f"  Provider: {current_model['provider']}")
        print(f"  Model: {current_model['model_name']}")
        print(f"  Dimension: {current_model['dimension']}")

        # 3. 获取数据库中的模型
        print("\n[数据库记录]")
        vector_search = VectorSearchService(db_path)

        db_provider = vector_search.get_metadata("model_provider")
        db_model = vector_search.get_metadata("model_name")
        db_dimension = vector_search.get_metadata("dimension")

        if not db_model:
            print("  ⚠️  数据库中没有模型记录（可能是首次运行）")
            print("  建议运行: python -m backend.scripts.rebuild_embeddings")
            return 0

        print(f"  Provider: {db_provider}")
        print(f"  Model: {db_model}")
        print(f"  Dimension: {db_dimension}")

        # 4. 检查一致性
        print("\n[一致性检查]")
        is_consistent = (
            current_model["provider"] == db_provider and
            current_model["model_name"] == db_model and
            str(current_model["dimension"]) == db_dimension
        )

        if is_consistent:
            print("  ✅ 模型配置一致")
        else:
            print("  ❌ 模型配置不一致！")
            print("\n  当前配置和数据库中的模型不匹配。")
            print("  这会导致检索结果不准确。")
            print("\n  解决方法：")
            print("    python -m backend.scripts.rebuild_embeddings")
            return 1

        # 5. 显示统计信息
        print("\n[统计信息]")
        stats = vector_search.get_stats()
        print(f"  总消息数: {stats['total_messages']}")
        print(f"  应有 embedding: {stats['should_have_embeddings']}")
        print(f"  现有 embedding: {stats['total_embeddings']}")
        print(f"  缺失 embedding: {stats['missing_embeddings']}")

        if stats['missing_embeddings'] > 0:
            print(f"\n  ⚠️  有 {stats['missing_embeddings']} 条消息缺失 embedding")
            print("  建议运行: python -m backend.scripts.rebuild_embeddings")

        print("\n" + "=" * 60)
        return 0

    except Exception as e:
        logger.error(f"检查失败: {e}", exc_info=True)
        print(f"\n❌ 检查失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
