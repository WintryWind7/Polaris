"""
Embedding 模型检测器

扫描 data/models/embeddings/ 目录，识别可用的本地模型
"""
import json
from pathlib import Path
from typing import List, Dict, Optional


class EmbeddingDetector:
    """本地 Embedding 模型检测器"""

    def __init__(self, models_dir: Path):
        self.models_dir = models_dir

    def scan_models(self) -> List[Dict]:
        """
        扫描所有可用的模型

        Returns:
            [
                {
                    "model_id": "bge-small-zh-v1.5",
                    "model_path": "data/models/embeddings/bge-small-zh-v1.5",
                    "dimension": 384,
                    "model_type": "bert",
                    "weight_format": "safetensors",  # 或 "pytorch"
                    "weight_size_mb": 95.2,
                    "valid": True,
                    "error": None
                },
                ...
            ]
        """
        if not self.models_dir.exists():
            return []

        models = []
        for model_dir in self.models_dir.iterdir():
            if not model_dir.is_dir():
                continue

            # 跳过隐藏目录和特殊目录
            if model_dir.name.startswith('.') or model_dir.name.startswith('_'):
                continue

            model_info = self._detect_model(model_dir)
            if model_info:
                models.append(model_info)

        return models

    def _detect_model(self, model_dir: Path) -> Optional[Dict]:
        """
        检测单个模型目录

        Args:
            model_dir: 模型目录路径

        Returns:
            模型信息字典，如果无效则返回 None
        """
        model_id = model_dir.name
        result = {
            "model_id": model_id,
            "model_path": str(model_dir.absolute()),
            "dimension": None,
            "model_type": None,
            "weight_format": None,
            "weight_size_mb": None,
            "valid": False,
            "error": None
        }

        try:
            # 1. 检查 config.json（必需）
            config_file = model_dir / "config.json"
            if not config_file.exists():
                result["error"] = "缺少 config.json"
                return result

            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            result["dimension"] = config.get("hidden_size", 768)
            result["model_type"] = config.get("model_type", "unknown")

            # 2. 检查 tokenizer（必需，多种格式）
            tokenizer_files = [
                model_dir / "tokenizer.json",
                model_dir / "vocab.txt",
                model_dir / "tokenizer_config.json"
            ]
            if not any(f.exists() for f in tokenizer_files):
                result["error"] = "缺少 tokenizer 文件"
                return result

            # 3. 检查权重文件（必需，优先 safetensors）
            safetensors_file = model_dir / "model.safetensors"
            pytorch_file = model_dir / "pytorch_model.bin"

            if safetensors_file.exists():
                result["weight_format"] = "safetensors"
                result["weight_size_mb"] = round(safetensors_file.stat().st_size / 1024 / 1024, 2)
            elif pytorch_file.exists():
                result["weight_format"] = "pytorch"
                result["weight_size_mb"] = round(pytorch_file.stat().st_size / 1024 / 1024, 2)
            else:
                result["error"] = "缺少权重文件 (model.safetensors 或 pytorch_model.bin)"
                return result

            # 4. 所有检查通过
            result["valid"] = True
            result["error"] = None

        except json.JSONDecodeError:
            result["error"] = "config.json 格式错误"
        except Exception as e:
            result["error"] = f"检测失败: {str(e)}"

        return result

    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """获取指定模型的详细信息"""
        model_dir = self.models_dir / model_id
        if not model_dir.exists():
            return None

        return self._detect_model(model_dir)


# 便捷函数
def scan_local_models(base_dir: Optional[Path] = None) -> List[Dict]:
    """
    扫描本地模型

    Args:
        base_dir: 项目根目录，默认为当前工作目录

    Returns:
        模型列表
    """
    if base_dir is None:
        base_dir = Path.cwd()

    models_dir = base_dir / "backend" / "data" / "models" / "embeddings"
    detector = EmbeddingDetector(models_dir)
    return detector.scan_models()
