import tkinter as tk
from tkinter import ttk, messagebox
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path


class TranslatorUI:
    def _open_system_config_window(self) -> None:
        if hasattr(self, 'system_config_window') and self.system_config_window is not None and self.system_config_window.winfo_exists():
            self.system_config_window.focus_set()
            return

        import tkinter.font as tkfont
        window = tk.Toplevel(self.root)
        window.title("系统配置")
        window.geometry("400x220")
        window.minsize(320, 180)
        window.transient(self.root)
        window.grab_set()
        self.system_config_window = window

        outer = ttk.Frame(window, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="界面字体:").grid(row=0, column=0, sticky="w", pady=8)
        font_families = sorted(set(tkfont.families()))
        font_combo = ttk.Combobox(outer, textvariable=self.font_family_var, values=font_families, state="readonly", width=24)
        font_combo.grid(row=0, column=1, sticky="w", pady=8)

        ttk.Label(outer, text="字号:").grid(row=1, column=0, sticky="w", pady=8)
        font_size_spin = ttk.Spinbox(outer, from_=8, to=36, textvariable=self.font_size_var, width=6)
        font_size_spin.grid(row=1, column=1, sticky="w", pady=8)

        def save_font():
            family = self.font_family_var.get()
            size = self.font_size_var.get()
            self.default_font = (family, int(size))
            self._apply_font_to_widgets()
            messagebox.showinfo("提示", f"字体已应用: {family} {size}")

        action_row = ttk.Frame(outer)
        action_row.grid(row=2, column=0, columnspan=2, pady=(16, 0), sticky="e")
        ttk.Button(action_row, text="应用", command=save_font).pack(side="right", padx=(0, 8))
        ttk.Button(action_row, text="关闭", command=window.destroy).pack(side="right")

        window.protocol("WM_DELETE_WINDOW", window.destroy)

    def _detect_and_set_font(self):
        import tkinter.font as tkfont
        self.font_candidates = [
            ("WenQuanYi Zen Hei", 12),
            ("Noto Sans CJK SC", 12),
            ("Microsoft YaHei", 12),
            ("SimSun", 12),
            ("Arial", 12),
            ("sans-serif", 12),
        ]
        self.font_family_var = tk.StringVar()
        self.font_size_var = tk.IntVar()
        available_fonts = set(tkfont.families())
        for family, size in self.font_candidates:
            if family in available_fonts:
                self.font_family_var.set(family)
                self.font_size_var.set(size)
                self.default_font = (family, size)
                break
        else:
            self.font_family_var.set("Arial")
            self.font_size_var.set(12)
            self.default_font = ("Arial", 12)

    def _apply_font_to_widgets(self):
        # 只对主要 Text 控件和提示词配置 Text 应用字体
        if hasattr(self, "input_text"):
            self.input_text.config(font=self.default_font)
        if hasattr(self, "output_text"):
            self.output_text.config(font=self.default_font)
        if hasattr(self, "prompt_text_widget"):
            self.prompt_text_widget.config(font=self.default_font)

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Wiki 翻译工具")
        self.root.geometry("1000x620")
        self.root.minsize(900, 560)
        self.config_path = Path(__file__).with_name("translator_config.json")

        self.input_chunks: list[str] = []
        self.current_index = 0
        self.output_buffer: list[str] = []

        self.provider_var = tk.StringVar(value="local")
        self.local_provider_var = tk.StringVar(value="ollama")
        self.ollama_host_var = tk.StringVar(value="http://127.0.0.1:11434")
        self.ollama_model_var = tk.StringVar(value="qwen2.5:7b")
        self.ollama_timeout_var = tk.StringVar(value="20")

        self.cloud_base_url_var = tk.StringVar(value="https://api.openai.com/v1")
        self.cloud_api_key_var = tk.StringVar(value="")
        self.cloud_model_var = tk.StringVar(value="gpt-4o-mini")
        self.cloud_timeout_var = tk.StringVar(value="20")
        self.test_status_var = tk.StringVar(value="")

        self.model_config_window: tk.Toplevel | None = None
        self.local_frame: ttk.Frame | None = None
        self.cloud_frame: ttk.Frame | None = None
        self.test_button: ttk.Button | None = None
        self.confirm_button: ttk.Button | None = None
        self.status_label_widget: ttk.Label | None = None
        self._config_ready = False

        self._detect_and_set_font()
        self._load_or_create_config()
        self._bind_config_autosave()
        self._config_ready = True
        self._save_config_file()

        self._build_menu()
        self._build_main_layout()

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)

        config_menu = tk.Menu(menu_bar, tearoff=0)
        config_menu.add_command(label="模型配置", command=self._open_model_config_window)
        config_menu.add_command(label="提示词配置", command=self._open_prompt_config_window)
        config_menu.add_command(label="术语配置", command=self._todo_dialog)
        config_menu.add_command(label="输出配置", command=self._todo_dialog)
        menu_bar.add_cascade(label="配置", menu=config_menu)

        system_menu = tk.Menu(menu_bar, tearoff=0)
        system_menu.add_command(label="系统配置", command=self._open_system_config_window)
        menu_bar.add_cascade(label="系统", menu=system_menu)

        tools_menu = tk.Menu(menu_bar, tearoff=0)
        tools_menu.add_command(label="清空输入", command=self._clear_input)
        tools_menu.add_command(label="清空输出", command=self._clear_output)
        tools_menu.add_separator()
        tools_menu.add_command(label="全部清空", command=self._clear_all)
        menu_bar.add_cascade(label="工具", menu=tools_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        menu_bar.add_cascade(label="帮助", menu=help_menu)

        self.root.config(menu=menu_bar)

    def _open_prompt_config_window(self) -> None:
        if hasattr(self, 'prompt_config_window') and self.prompt_config_window is not None and self.prompt_config_window.winfo_exists():
            self.prompt_config_window.focus_set()
            return

        window = tk.Toplevel(self.root)
        window.title("提示词配置")
        window.geometry("600x400")
        window.minsize(480, 320)
        window.transient(self.root)
        window.grab_set()
        self.prompt_config_window = window

        outer = ttk.Frame(window, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="请输入提示词（Prompt）:").pack(anchor="w", pady=(0, 6))
        self.prompt_var = tk.StringVar()
        self.prompt_text_widget = tk.Text(outer, wrap="word", font=self.default_font, height=10)
        self.prompt_text_widget.pack(fill="both", expand=True, padx=4, pady=4)

        # 加载已有提示词
        config_data = self._collect_config()
        prompt_value = config_data.get("prompt", "")
        self.prompt_text_widget.insert("1.0", prompt_value)

        def save_prompt():
            value = self.prompt_text_widget.get("1.0", "end-1c").strip()
            self._save_prompt_to_config(value)
            messagebox.showinfo("提示", "提示词已保存。")

        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=(10, 0))
        ttk.Button(action_row, text="保存", command=save_prompt).pack(side="right", padx=(0, 8))
        ttk.Button(action_row, text="关闭", command=window.destroy).pack(side="right")

        window.protocol("WM_DELETE_WINDOW", window.destroy)

    def _save_prompt_to_config(self, prompt: str) -> None:
        config_data = self._collect_config()
        config_data["prompt"] = prompt
        self.config_path.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ...existing code...

    def _build_main_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        text_panel = ttk.Frame(outer)
        text_panel.pack(fill="both", expand=True)

        left_frame = ttk.LabelFrame(text_panel, text="原文输入")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right_frame = ttk.LabelFrame(text_panel, text="翻译结果")
        right_frame.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self.input_text = tk.Text(left_frame, wrap="word", font=self.default_font, undo=True)
        self.input_text.pack(fill="both", expand=True, padx=8, pady=8)

        self.output_text = tk.Text(right_frame, wrap="word", font=self.default_font, state="disabled")
        self.output_text.pack(fill="both", expand=True, padx=8, pady=8)

        control_panel = ttk.Frame(outer)
        control_panel.pack(fill="x", pady=(12, 0))

        self.start_button = ttk.Button(control_panel, text="开始翻译", command=self.start_translation)
        self.start_button.pack(side="left")

        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(
            control_panel,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress.pack(side="left", fill="x", expand=True, padx=(12, 0))

        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(outer, textvariable=self.status_var, anchor="w")
        self.status_label.pack(fill="x", pady=(8, 0))

    def start_translation(self) -> None:
        raw_text = self.input_text.get("1.0", "end-1c").strip()
        if not raw_text:
            messagebox.showwarning("提示", "请先粘贴待翻译文本。")
            return

        self.input_chunks = self._split_text(raw_text)
        self.current_index = 0
        self.output_buffer = []
        self.progress_var.set(0)
        self._set_output_text("")

        self.start_button.config(state="disabled")
        self.status_var.set("翻译中...")
        self.root.after(80, self._translate_step)

    def _translate_step(self) -> None:
        if self.current_index >= len(self.input_chunks):
            self.progress_var.set(100)
            self.start_button.config(state="normal")
            self.status_var.set("翻译完成")
            return

        chunk = self.input_chunks[self.current_index]
        translated = self._mock_translate(chunk)
        self.output_buffer.append(translated)

        self._set_output_text("".join(self.output_buffer))

        self.current_index += 1
        progress = (self.current_index / len(self.input_chunks)) * 100
        self.progress_var.set(progress)
        self.status_var.set(f"翻译中... {self.current_index}/{len(self.input_chunks)}")

        self.root.after(80, self._translate_step)

    def _open_model_config_window(self) -> None:
        if self.model_config_window is not None and self.model_config_window.winfo_exists():
            self.model_config_window.focus_set()
            return

        window = tk.Toplevel(self.root)
        window.title("模型配置")
        window.geometry("700x620")
        window.minsize(680, 600)
        window.transient(self.root)
        window.grab_set()

        self.model_config_window = window
        self.test_status_var.set("")

        outer = ttk.Frame(window, padding=12)
        outer.pack(fill="both", expand=True)

        mode_frame = ttk.LabelFrame(outer, text="模型来源")
        mode_frame.pack(fill="x")
        ttk.Radiobutton(mode_frame, text="本地模型", value="local", variable=self.provider_var, command=self._refresh_model_provider_ui).pack(side="left", padx=8, pady=8)
        ttk.Radiobutton(mode_frame, text="云端模型", value="cloud", variable=self.provider_var, command=self._refresh_model_provider_ui).pack(side="left", padx=8, pady=8)

        self.local_frame = ttk.LabelFrame(outer, text="本地模型设置")
        self.local_frame.pack(fill="x", pady=(10, 0))
        self._build_local_fields(self.local_frame)

        self.cloud_frame = ttk.LabelFrame(outer, text="云端模型设置")
        self.cloud_frame.pack(fill="x", pady=(10, 0))
        self._build_cloud_fields(self.cloud_frame)

        test_frame = ttk.LabelFrame(outer, text="连接测试")
        test_frame.pack(fill="x", pady=(10, 0))

        self.test_button = ttk.Button(test_frame, text="测试模型是否可用", command=self._start_model_test)
        self.test_button.pack(anchor="w", padx=8, pady=(8, 4))

        self.status_label_widget = ttk.Label(test_frame, textvariable=self.test_status_var, anchor="w", foreground="#1f2937")
        self.status_label_widget.pack(fill="x", padx=8, pady=(0, 8))

        tip = (
            "提示:\n"
            "1. 本地 Ollama 测试会请求 /api/tags 和 /api/generate。\n"
            "2. 云端测试会请求 /models 端点验证可用性。"
        )
        ttk.Label(test_frame, text=tip, justify="left").pack(anchor="w", padx=8, pady=(0, 8))

        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=(10, 0))
        ttk.Button(action_row, text="保存配置", command=self._save_config_by_button).pack(side="right", padx=(0, 8))
        self.confirm_button = ttk.Button(action_row, text="确认并关闭", command=self._on_model_window_close)
        self.confirm_button.pack(side="right")

        window.protocol("WM_DELETE_WINDOW", self._on_model_window_close)
        self._refresh_model_provider_ui()

    def _build_local_fields(self, frame: ttk.LabelFrame) -> None:
        ttk.Label(frame, text="本地服务").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        local_provider_box = ttk.Combobox(frame, textvariable=self.local_provider_var, values=["ollama"], state="readonly", width=18)
        local_provider_box.grid(row=0, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(frame, text="Ollama 地址").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.ollama_host_var, width=46).grid(row=1, column=1, sticky="we", padx=8, pady=6)

        ttk.Label(frame, text="模型名称").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.ollama_model_var, width=46).grid(row=2, column=1, sticky="we", padx=8, pady=6)

        ttk.Label(frame, text="超时(秒)").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.ollama_timeout_var, width=10).grid(row=3, column=1, sticky="w", padx=8, pady=6)

        frame.grid_columnconfigure(1, weight=1)

    def _build_cloud_fields(self, frame: ttk.LabelFrame) -> None:
        ttk.Label(frame, text="接口地址").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.cloud_base_url_var, width=46).grid(row=0, column=1, sticky="we", padx=8, pady=6)

        ttk.Label(frame, text="API Key").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.cloud_api_key_var, width=46, show="*").grid(row=1, column=1, sticky="we", padx=8, pady=6)

        ttk.Label(frame, text="模型名称").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.cloud_model_var, width=46).grid(row=2, column=1, sticky="we", padx=8, pady=6)

        ttk.Label(frame, text="超时(秒)").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.cloud_timeout_var, width=10).grid(row=3, column=1, sticky="w", padx=8, pady=6)

        frame.grid_columnconfigure(1, weight=1)

    def _refresh_model_provider_ui(self) -> None:
        if self.local_frame is None or self.cloud_frame is None:
            return

        if self.provider_var.get() == "local":
            self._set_children_state(self.local_frame, enabled=True)
            self._set_children_state(self.cloud_frame, enabled=False)
        else:
            self._set_children_state(self.local_frame, enabled=False)
            self._set_children_state(self.cloud_frame, enabled=True)

    def _set_children_state(self, container: tk.Misc, enabled: bool) -> None:
        target_state = "normal" if enabled else "disabled"
        readonly_state = "readonly" if enabled else "disabled"
        for child in container.winfo_children():
            if isinstance(child, ttk.Combobox):
                child.configure(state=readonly_state)
            elif isinstance(child, (ttk.Entry, ttk.Radiobutton, ttk.Button, ttk.Checkbutton)):
                child.configure(state=target_state)
            self._set_children_state(child, enabled)

    def _load_or_create_config(self) -> None:
        if self.config_path.exists():
            try:
                config_data = json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                config_data = self._default_config()
                self.config_path.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            config_data = self._default_config()
            self.config_path.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")

        self._apply_config(config_data)

    def _bind_config_autosave(self) -> None:
        watched_vars = [
            self.provider_var,
            self.local_provider_var,
            self.ollama_host_var,
            self.ollama_model_var,
            self.ollama_timeout_var,
            self.cloud_base_url_var,
            self.cloud_api_key_var,
            self.cloud_model_var,
            self.cloud_timeout_var,
        ]
        for var in watched_vars:
            var.trace_add("write", self._on_config_changed)

    def _on_config_changed(self, *_: object) -> None:
        if not self._config_ready:
            return
        self._save_config_file()

    def _save_config_by_button(self) -> None:
        self._save_config_file()
        self.test_status_var.set("配置已保存")

    def _save_config_file(self) -> None:
        config_data = self._collect_config()
        self.config_path.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _collect_config(self) -> dict:
        # 读取现有配置，保留 prompt 字段
        if self.config_path.exists():
            try:
                config_data = json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                config_data = {}
        else:
            config_data = {}
        config_data.update({
            "provider": self.provider_var.get(),
            "local_provider": self.local_provider_var.get(),
            "ollama": {
                "host": self.ollama_host_var.get(),
                "model": self.ollama_model_var.get(),
                "timeout": self.ollama_timeout_var.get(),
            },
            "cloud": {
                "base_url": self.cloud_base_url_var.get(),
                "api_key": self.cloud_api_key_var.get(),
                "model": self.cloud_model_var.get(),
                "timeout": self.cloud_timeout_var.get(),
            },
        })
        return config_data

    def _apply_config(self, config_data: dict) -> None:
        defaults = self._default_config()
        merged = {
            **defaults,
            **config_data,
            "ollama": {**defaults["ollama"], **config_data.get("ollama", {})},
            "cloud": {**defaults["cloud"], **config_data.get("cloud", {})},
        }

        self.provider_var.set(str(merged.get("provider", "local")))
        self.local_provider_var.set(str(merged.get("local_provider", "ollama")))
        self.ollama_host_var.set(str(merged["ollama"].get("host", "http://127.0.0.1:11434")))
        self.ollama_model_var.set(str(merged["ollama"].get("model", "qwen2.5:7b")))
        self.ollama_timeout_var.set(str(merged["ollama"].get("timeout", "20")))
        self.cloud_base_url_var.set(str(merged["cloud"].get("base_url", "https://api.openai.com/v1")))
        self.cloud_api_key_var.set(str(merged["cloud"].get("api_key", "")))
        self.cloud_model_var.set(str(merged["cloud"].get("model", "gpt-4o-mini")))
        self.cloud_timeout_var.set(str(merged["cloud"].get("timeout", "20")))

    @staticmethod
    def _default_config() -> dict:
        return {
            "provider": "local",
            "local_provider": "ollama",
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
        }

    def _start_model_test(self) -> None:
        if self.test_button is not None:
            self.test_button.config(state="disabled")

        self.test_status_var.set("测试中，请稍候...")
        threading.Thread(target=self._run_model_test, daemon=True).start()

    def _run_model_test(self) -> None:
        try:
            if self.provider_var.get() == "local":
                result = self._test_ollama_connection()
            else:
                result = self._test_cloud_connection()
            self.root.after(0, self._finish_model_test, True, result)
        except Exception as exc:
            self.root.after(0, self._finish_model_test, False, f"测试失败: {exc}")

    def _finish_model_test(self, success: bool, text: str) -> None:
        self.test_status_var.set(text)
        if self.test_button is not None:
            self.test_button.config(state="normal")

        if self.status_label_widget is not None:
            self.status_label_widget.config(foreground="#0f5132" if success else "#842029")

    def _test_ollama_connection(self) -> str:
        host = self.ollama_host_var.get().strip().rstrip("/")
        model = self.ollama_model_var.get().strip()
        timeout = self._parse_timeout(self.ollama_timeout_var.get())

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

    def _test_cloud_connection(self) -> str:
        base_url = self.cloud_base_url_var.get().strip().rstrip("/")
        api_key = self.cloud_api_key_var.get().strip()
        model = self.cloud_model_var.get().strip()
        timeout = self._parse_timeout(self.cloud_timeout_var.get())

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
    def _parse_timeout(raw_text: str) -> float:
        value = raw_text.strip()
        if not value:
            return 20.0
        timeout = float(value)
        if timeout <= 0:
            raise ValueError("超时必须大于 0")
        return timeout

    def _on_model_window_close(self) -> None:
        self._save_config_file()
        if self.model_config_window is not None and self.model_config_window.winfo_exists():
            self.model_config_window.destroy()
        self.model_config_window = None

    @staticmethod
    def _split_text(text: str, chunk_size: int = 220) -> list[str]:
        chunks = []
        start = 0
        while start < len(text):
            chunks.append(text[start:start + chunk_size])
            start += chunk_size
        return chunks

    @staticmethod
    def _mock_translate(chunk: str) -> str:
        # 预留真实翻译调用位置：后续可替换为本地LLM接口。
        return chunk

    def _set_output_text(self, content: str) -> None:
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", content)
        self.output_text.config(state="disabled")

    @staticmethod
    def _todo_dialog() -> None:
        messagebox.showinfo("待实现", "该配置页面留作后续扩展。")

    def _clear_input(self) -> None:
        self.input_text.delete("1.0", "end")

    def _clear_output(self) -> None:
        self._set_output_text("")

    def _clear_all(self) -> None:
        self._clear_input()
        self._clear_output()
        self.progress_var.set(0)
        self.status_var.set("就绪")

    @staticmethod
    def _show_about() -> None:
        messagebox.showinfo("关于", "Wiki 翻译工具 UI 原型\n用于后续接入本地大模型翻译。")


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    app = TranslatorUI(root)
    _ = app
    root.mainloop()


if __name__ == "__main__":
    main()
