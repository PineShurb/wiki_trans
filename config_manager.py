import json
from pathlib import Path


class ConfigManager:
    DEFAULT_TRANSLATION_PROMPT = (
        "你是用于 wiki 文档续译与校订的专业翻译助手。请严格按以下规则处理【待翻译文本】:\n"
        "1. 将原文逐句翻译为中文，尽量保持原句顺序，不合并、不随意拆分句子；保留原有段落、列表、标点、Markdown、链接、代码和占位符格式。\n"
        "2. 如果提供了【术语要求】，必须优先采用其中术语译法，并在全文保持一致。\n"
        "3. 如果提供了【参考文本】，将其视为已有译文基线，优先在其基础上继续翻译，并尽量复用其中已经正确的句子、措辞和风格。\n"
        "4. 变更最小化：若原文与参考文本中对应句子的译文准确、自然、无明显错误，则直接沿用，不要改写；仅在发现错译、漏译、术语不一致、语义不通或格式问题时才调整。\n"
        "5. 若参考文本与原文不完全对应，或只有部分可用，仅复用能对应的内容；其余部分按相同风格补全翻译。\n"
        "6. 只输出最终译文，不要解释、不要添加说明、不要补充原文中没有的信息。"
    )

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    @staticmethod
    def default_config() -> dict:
        return {
            "provider": "local",
            "local_provider": "ollama",
            "system": {
                "font_family": "Arial",
                "font_size": 12,
            },
            "ollama": {
                "host": "http://127.0.0.1:11434",
                "model": "qwen2.5:7b",
                "timeout": "20",
            },
            "cloud": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o-mini",
                "timeout": "20",
            },
            "prompt": ConfigManager.DEFAULT_TRANSLATION_PROMPT,
            "terminology_path": "",
            "reference_text": "",
        }

    def read(self) -> dict:
        if not self.config_path.exists():
            return {}
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, config_data: dict) -> None:
        self.config_path.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_merged(self) -> dict:
        return self._merge_with_defaults(self.read())

    def load_or_create(self) -> dict:
        stored = self.read()
        merged = self.read_merged()
        if not stored:
            self.save(merged)
        return merged

    def _merge_with_defaults(self, config_data: dict) -> dict:
        defaults = self.default_config()
        return {
            **defaults,
            **config_data,
            "system": {**defaults["system"], **config_data.get("system", {})},
            "ollama": {**defaults["ollama"], **config_data.get("ollama", {})},
            "cloud": {**defaults["cloud"], **config_data.get("cloud", {})},
        }
