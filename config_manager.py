import json
from pathlib import Path


class ConfigManager:
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
            "prompt": "",
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

    def load_or_create(self) -> dict:
        stored = self.read()
        merged = self._merge_with_defaults(stored)
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
