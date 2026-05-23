from collections.abc import Callable
import json
import socket
import urllib.error
import urllib.request


class TranslatorGateway:
    @staticmethod
    def _timeout_hint(timeout: float | None) -> str:
        if timeout is None:
            return "未设置超时"
        return f"{timeout:g} 秒"

    @staticmethod
    def _is_timeout_error(exc: Exception) -> bool:
        if isinstance(exc, (TimeoutError, socket.timeout)):
            return True
        if isinstance(exc, urllib.error.URLError):
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                return True
            return "timed out" in str(reason).casefold()
        return "timed out" in str(exc).casefold()

    @staticmethod
    def _build_request_error(service: str, exc: Exception, timeout: float | None) -> Exception:
        if isinstance(exc, urllib.error.HTTPError):
            detail = exc.read().decode("utf-8", errors="ignore")
            return RuntimeError(f"{service} 接口错误 {exc.code}: {detail[:200]}")
        if TranslatorGateway._is_timeout_error(exc):
            return TimeoutError(
                f"{service} 请求超时（{TranslatorGateway._timeout_hint(timeout)}）。当前请求可能过大，或模型响应较慢。"
            )
        if isinstance(exc, urllib.error.URLError):
            return RuntimeError(f"{service} 网络请求失败: {exc.reason}")
        return exc

    @staticmethod
    def _urlopen(request: urllib.request.Request, timeout: float | None = None):
        if timeout is None:
            return urllib.request.urlopen(request)
        return urllib.request.urlopen(request, timeout=timeout)

    @staticmethod
    def _build_ollama_request(host: str, model: str, text: str, stream: bool) -> urllib.request.Request:
        host = host.strip().rstrip("/")
        model = model.strip()
        if not host or not model:
            raise ValueError("Ollama 配置缺失")

        url = f"{host}/api/generate"
        payload = json.dumps({
            "model": model,
            "prompt": text,
            "stream": stream,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        return req

    @staticmethod
    def translate_ollama(host: str, model: str, text: str, timeout: float | None = None) -> str:
        """
        调用本地 Ollama API 进行翻译。
        """
        req = TranslatorGateway._build_ollama_request(host, model, text, stream=False)
        try:
            with TranslatorGateway._urlopen(req, timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Ollama 生成失败，状态码 {resp.status}")
                body = resp.read().decode("utf-8")
                data = json.loads(body)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise TranslatorGateway._build_request_error("Ollama", exc, timeout) from exc
        return data.get("response", "")

    @staticmethod
    def translate_ollama_stream(
        host: str,
        model: str,
        text: str,
        on_chunk: Callable[[str], None],
        timeout: float | None = None,
    ) -> str:
        req = TranslatorGateway._build_ollama_request(host, model, text, stream=True)
        chunks: list[str] = []
        try:
            with TranslatorGateway._urlopen(req, timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Ollama 生成失败，状态码 {resp.status}")

                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError("Ollama 流式响应解析失败") from exc

                    if data.get("error"):
                        raise RuntimeError(str(data["error"]))

                    chunk = data.get("response", "")
                    if not chunk:
                        continue

                    chunks.append(chunk)
                    on_chunk(chunk)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise TranslatorGateway._build_request_error("Ollama", exc, timeout) from exc

        return "".join(chunks)

    @staticmethod
    def translate_cloud(base_url: str, api_key: str, model: str, text: str, timeout: float | None = None) -> str:
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
        try:
            with TranslatorGateway._urlopen(req, timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"云端生成失败，状态码 {resp.status}")
                body = resp.read().decode("utf-8")
                data = json.loads(body)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise TranslatorGateway._build_request_error("云端接口", exc, timeout) from exc
        # OpenAI兼容接口返回choices
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""
    @staticmethod
    def test_ollama_connection(host: str, model: str, timeout: float | None) -> str:
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

        return f"本地 Ollama 服务连接成功，模型已安装: {model}"

    @staticmethod
    def test_ollama_inference(host: str, model: str, timeout: float | None) -> str:
        gen_req = TranslatorGateway._build_ollama_request(host, model, "ping", stream=False)
        with TranslatorGateway._urlopen(gen_req, timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"访问 /api/generate 失败，状态码 {resp.status}")
            body = resp.read().decode("utf-8")
            data = json.loads(body)

        if data.get("error"):
            raise RuntimeError(str(data["error"]))

        return f"本地 Ollama 推理可用: {model}"

    @staticmethod
    def test_cloud_connection(base_url: str, api_key: str, model: str, timeout: float | None) -> str:
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

    @staticmethod
    def test_cloud_inference(base_url: str, api_key: str, model: str, timeout: float | None) -> str:
        base_url = base_url.strip().rstrip("/")
        api_key = api_key.strip()
        model = model.strip()

        if not base_url:
            raise ValueError("请填写云端接口地址")
        if not api_key:
            raise ValueError("请填写 API Key")
        if not model:
            raise ValueError("请填写云端模型名称")

        url = f"{base_url}/chat/completions"
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": "Reply with pong."},
            ],
            "max_tokens": 8,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")

        try:
            with TranslatorGateway._urlopen(req, timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"访问 /chat/completions 失败，状态码 {resp.status}")
                body = resp.read().decode("utf-8")
                data = json.loads(body)
        except urllib.error.HTTPError as http_err:
            detail = http_err.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"云端接口错误 {http_err.code}: {detail[:200]}") from http_err

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("云端推理未返回结果")

        return f"云端模型推理可用: {model}"
