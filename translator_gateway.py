import json
import urllib.error
import urllib.request


class TranslatorGateway:
    @staticmethod
    def translate_ollama(host: str, model: str, text: str, timeout: float) -> str:
        """
        调用本地 Ollama API 进行翻译。
        """
        host = host.strip().rstrip("/")
        model = model.strip()
        if not host or not model:
            raise ValueError("Ollama 配置缺失")
        url = f"{host}/api/generate"
        payload = json.dumps({
            "model": model,
            "prompt": text,
            "stream": False
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ollama 生成失败，状态码 {resp.status}")
            body = resp.read().decode("utf-8")
            data = json.loads(body)
        return data.get("response", "")

    @staticmethod
    def translate_cloud(base_url: str, api_key: str, model: str, text: str, timeout: float) -> str:
        """
        调用云端 API 进行翻译（如OpenAI兼容接口）。
        """
        base_url = base_url.strip().rstrip("/")
        api_key = api_key.strip()
        model = model.strip()
        if not base_url or not api_key or not model:
            raise ValueError("云端配置缺失")
        url = f"{base_url}/chat/completions"
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a translation assistant."},
                {"role": "user", "content": text}
            ],
            "stream": False
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"云端生成失败，状态码 {resp.status}")
            body = resp.read().decode("utf-8")
            data = json.loads(body)
        # OpenAI兼容接口返回choices
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""
    @staticmethod
    def test_ollama_connection(host: str, model: str, timeout: float) -> str:
        host = host.strip().rstrip("/")
        model = model.strip()

        if not host:
            raise ValueError("请填写 Ollama 地址")
        if not model:
            raise ValueError("请填写 Ollama 模型名称")

        tags_url = f"{host}/api/tags"
        tags_req = urllib.request.Request(tags_url, method="GET")
        with urllib.request.urlopen(tags_req, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"访问 /api/tags 失败，状态码 {resp.status}")
            body = resp.read().decode("utf-8")
            tags_data = json.loads(body)

        model_names = [item.get("name", "") for item in tags_data.get("models", [])]
        if model not in model_names:
            model_hint = "、".join(model_names[:8]) if model_names else "无"
            raise RuntimeError(f"本地未发现模型 {model}。当前模型: {model_hint}")

        generate_url = f"{host}/api/generate"
        payload = json.dumps({"model": model, "prompt": "ping", "stream": False}).encode("utf-8")
        gen_req = urllib.request.Request(generate_url, data=payload, method="POST")
        gen_req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(gen_req, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"访问 /api/generate 失败，状态码 {resp.status}")
            _ = resp.read()

        return f"本地 Ollama 模型可用: {model}"

    @staticmethod
    def test_cloud_connection(base_url: str, api_key: str, model: str, timeout: float) -> str:
        base_url = base_url.strip().rstrip("/")
        api_key = api_key.strip()
        model = model.strip()

        if not base_url:
            raise ValueError("请填写云端接口地址")
        if not api_key:
            raise ValueError("请填写 API Key")
        if not model:
            raise ValueError("请填写云端模型名称")

        models_url = f"{base_url}/models"
        req = urllib.request.Request(models_url, method="GET")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"访问 /models 失败，状态码 {resp.status}")
                body = resp.read().decode("utf-8")
                data = json.loads(body)
        except urllib.error.HTTPError as http_err:
            detail = http_err.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"云端接口错误 {http_err.code}: {detail[:200]}") from http_err

        ids = [item.get("id", "") for item in data.get("data", [])]
        if model not in ids:
            top = "、".join(ids[:8]) if ids else "无"
            return f"连接成功，但模型 {model} 未在列表中。可用模型示例: {top}"

        return f"云端模型可用: {model}"
