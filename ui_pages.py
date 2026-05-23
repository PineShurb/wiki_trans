import tkinter as tk
from tkinter import filedialog, ttk, messagebox


def open_system_config_window(app) -> None:
    if hasattr(app, "system_config_window") and app.system_config_window is not None and app.system_config_window.winfo_exists():
        app.system_config_window.focus_set()
        return

    import tkinter.font as tkfont

    window = tk.Toplevel(app.root)
    window.title("系统配置")
    window.geometry("400x220")
    window.minsize(320, 180)
    window.transient(app.root)
    window.grab_set()
    app.system_config_window = window

    outer = ttk.Frame(window, padding=16)
    outer.pack(fill="both", expand=True)

    ttk.Label(outer, text="界面字体:").grid(row=0, column=0, sticky="w", pady=8)
    font_families = sorted(set(tkfont.families()))
    font_combo = ttk.Combobox(outer, textvariable=app.font_family_var, values=font_families, state="readonly", width=24)
    font_combo.grid(row=0, column=1, sticky="w", pady=8)

    ttk.Label(outer, text="字号:").grid(row=1, column=0, sticky="w", pady=8)
    font_size_spin = ttk.Spinbox(outer, from_=8, to=36, textvariable=app.font_size_var, width=6)
    font_size_spin.grid(row=1, column=1, sticky="w", pady=8)

    def save_font() -> None:
        family = app.font_family_var.get()
        size = app.font_size_var.get()
        app.default_font = (family, int(size))
        app._apply_font_to_widgets()
        app._save_config_file()
        messagebox.showinfo("提示", f"字体已应用: {family} {size}")

    action_row = ttk.Frame(outer)
    action_row.grid(row=2, column=0, columnspan=2, pady=(16, 0), sticky="e")
    ttk.Button(action_row, text="应用", command=save_font).pack(side="right", padx=(0, 8))
    ttk.Button(action_row, text="关闭", command=window.destroy).pack(side="right")

    window.protocol("WM_DELETE_WINDOW", window.destroy)


def open_prompt_config_window(app) -> None:
    if hasattr(app, "prompt_config_window") and app.prompt_config_window is not None and app.prompt_config_window.winfo_exists():
        app.prompt_config_window.focus_set()
        return

    window = tk.Toplevel(app.root)
    window.title("提示词配置")
    window.geometry("600x400")
    window.minsize(480, 320)
    window.transient(app.root)
    window.grab_set()
    app.prompt_config_window = window

    outer = ttk.Frame(window, padding=12)
    outer.pack(fill="both", expand=True)

    ttk.Label(outer, text="请输入提示词（Prompt）:").pack(anchor="w", pady=(0, 6))
    app.prompt_var = tk.StringVar()
    app.prompt_text_widget = tk.Text(outer, wrap="word", font=app.default_font, height=10)
    app.prompt_text_widget.pack(fill="both", expand=True, padx=4, pady=4)

    config_data = app._collect_config()
    prompt_value = config_data.get("prompt", "")
    app.prompt_text_widget.insert("1.0", prompt_value)

    def save_prompt() -> None:
        value = app.prompt_text_widget.get("1.0", "end-1c").strip()
        app._save_prompt_to_config(value)
        messagebox.showinfo("提示", "提示词已保存。")

    action_row = ttk.Frame(outer)
    action_row.pack(fill="x", pady=(10, 0))
    ttk.Button(action_row, text="保存", command=save_prompt).pack(side="right", padx=(0, 8))
    ttk.Button(action_row, text="关闭", command=window.destroy).pack(side="right")

    window.protocol("WM_DELETE_WINDOW", window.destroy)


def open_terminology_config_window(app) -> None:
    if hasattr(app, "terminology_config_window") and app.terminology_config_window is not None and app.terminology_config_window.winfo_exists():
        app.terminology_config_window.focus_set()
        return

    window = tk.Toplevel(app.root)
    window.title("术语配置")
    window.geometry("720x260")
    window.minsize(620, 220)
    window.transient(app.root)
    window.grab_set()
    app.terminology_config_window = window

    outer = ttk.Frame(window, padding=12)
    outer.pack(fill="both", expand=True)

    ttk.Label(outer, text="术语表文件路径:").pack(anchor="w", pady=(0, 6))

    tip = (
        "推荐使用 TSV 文件，每行一条术语，列顺序为: source_term<TAB>target_term<TAB>note\n"
        "支持单词或词组，翻译时会按当前分块内容匹配命中的术语条目。\n"
        f"默认模板: {app.terminology_template_path.name}"
    )
    ttk.Label(outer, text=tip, justify="left").pack(anchor="w", padx=4, pady=(0, 6))

    path_row = ttk.Frame(outer)
    path_row.pack(fill="x", padx=4, pady=(0, 8))

    path_entry = ttk.Entry(path_row, textvariable=app.terminology_path_var)
    path_entry.pack(side="left", fill="x", expand=True)
    path_entry.bind("<Control-a>", app._select_all_text)
    path_entry.bind("<Control-A>", app._select_all_text)

    def browse_terminology_file() -> None:
        selected_path = filedialog.askopenfilename(
            title="选择术语表文件",
            initialdir=str(app.config_path.parent),
            filetypes=[("TSV 文件", "*.tsv"), ("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if selected_path:
            app.terminology_path_var.set(selected_path)

    ttk.Button(path_row, text="浏览", command=browse_terminology_file).pack(side="left", padx=(8, 0))

    helper_row = ttk.Frame(outer)
    helper_row.pack(fill="x", padx=4, pady=(0, 8))

    def use_template_path() -> None:
        app.terminology_path_var.set(app.terminology_template_path.name)

    ttk.Button(helper_row, text="使用模板路径", command=use_template_path).pack(side="left")

    def save_terminology() -> None:
        value = app.terminology_path_var.get().strip()
        app._save_terminology_to_config(value)
        messagebox.showinfo("提示", "术语配置已保存。")

    def close_window() -> None:
        app.terminology_config_window = None
        window.destroy()

    action_row = ttk.Frame(outer)
    action_row.pack(fill="x", pady=(10, 0))
    ttk.Button(action_row, text="保存", command=save_terminology).pack(side="right", padx=(0, 8))
    ttk.Button(action_row, text="关闭", command=close_window).pack(side="right")

    window.protocol("WM_DELETE_WINDOW", close_window)


class ModelConfigDialog:
    def __init__(self, app) -> None:
        self.app = app
        self.local_frame: ttk.LabelFrame | None = None
        self.cloud_frame: ttk.LabelFrame | None = None

    def open(self) -> None:
        if self.app.model_config_window is not None and self.app.model_config_window.winfo_exists():
            self.app.model_config_window.focus_set()
            return

        window = tk.Toplevel(self.app.root)
        window.title("模型配置")
        window.geometry("700x620")
        window.minsize(680, 600)
        window.transient(self.app.root)
        window.grab_set()

        self.app.model_config_window = window
        self.app.test_status_var.set("")

        outer = ttk.Frame(window, padding=12)
        outer.pack(fill="both", expand=True)

        mode_frame = ttk.LabelFrame(outer, text="模型来源")
        mode_frame.pack(fill="x")
        ttk.Radiobutton(
            mode_frame,
            text="本地模型",
            value="local",
            variable=self.app.provider_var,
            command=self._refresh_model_provider_ui,
        ).pack(side="left", padx=8, pady=8)
        ttk.Radiobutton(
            mode_frame,
            text="云端模型",
            value="cloud",
            variable=self.app.provider_var,
            command=self._refresh_model_provider_ui,
        ).pack(side="left", padx=8, pady=8)

        self.local_frame = ttk.LabelFrame(outer, text="本地模型设置")
        self.local_frame.pack(fill="x", pady=(10, 0))
        self._build_local_fields(self.local_frame)

        self.cloud_frame = ttk.LabelFrame(outer, text="云端模型设置")
        self.cloud_frame.pack(fill="x", pady=(10, 0))
        self._build_cloud_fields(self.cloud_frame)

        test_frame = ttk.LabelFrame(outer, text="连接测试")
        test_frame.pack(fill="x", pady=(10, 0))

        test_button_row = ttk.Frame(test_frame)
        test_button_row.pack(anchor="w", padx=8, pady=(8, 4))

        self.app.test_button = ttk.Button(test_button_row, text="测试连接与模型", command=self.app._start_model_test)
        self.app.test_button.pack(side="left")
        self.app.inference_test_button = ttk.Button(test_button_row, text="测试推理", command=self.app._start_model_inference_test)
        self.app.inference_test_button.pack(side="left", padx=(8, 0))

        self.app.status_label_widget = ttk.Label(test_frame, textvariable=self.app.test_status_var, anchor="w", foreground="#1f2937")
        self.app.status_label_widget.pack(fill="x", padx=8, pady=(0, 8))

        tip = (
            "提示:\n"
            "1. 测试连接与模型只检查服务连通性和模型是否存在，不触发真实推理。\n"
            "2. 测试推理会发送一次最小请求；本地 Ollama 会请求 /api/generate，云端会请求 /chat/completions。\n"
            "3. 大模型首次加载较慢，推理测试可能需要更长超时，云端推理测试也可能产生少量 token 消耗。"
        )
        ttk.Label(test_frame, text=tip, justify="left").pack(anchor="w", padx=8, pady=(0, 8))

        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=(10, 0))
        ttk.Button(action_row, text="保存配置", command=self.app._save_config_by_button).pack(side="right", padx=(0, 8))
        self.app.confirm_button = ttk.Button(action_row, text="确认并关闭", command=self.app._on_model_window_close)
        self.app.confirm_button.pack(side="right")

        window.protocol("WM_DELETE_WINDOW", self.app._on_model_window_close)
        self._refresh_model_provider_ui()

    def _build_local_fields(self, frame: ttk.LabelFrame) -> None:
        ttk.Label(frame, text="本地服务").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        local_provider_box = ttk.Combobox(frame, textvariable=self.app.local_provider_var, values=["ollama"], state="readonly", width=18)
        local_provider_box.grid(row=0, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(frame, text="Ollama 地址").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.app.ollama_host_var, width=46).grid(row=1, column=1, sticky="we", padx=8, pady=6)

        ttk.Label(frame, text="模型名称").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.app.ollama_model_var, width=46).grid(row=2, column=1, sticky="we", padx=8, pady=6)

        ttk.Label(frame, text="请求超时(秒)").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.app.ollama_timeout_var, width=10).grid(row=3, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(frame, text="留空或 0 表示不限时", foreground="#4b5563").grid(row=4, column=1, sticky="w", padx=8, pady=(0, 6))

        frame.grid_columnconfigure(1, weight=1)

    def _build_cloud_fields(self, frame: ttk.LabelFrame) -> None:
        ttk.Label(frame, text="接口地址").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.app.cloud_base_url_var, width=46).grid(row=0, column=1, sticky="we", padx=8, pady=6)

        ttk.Label(frame, text="API Key").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.app.cloud_api_key_var, width=46, show="*").grid(row=1, column=1, sticky="we", padx=8, pady=6)

        ttk.Label(frame, text="模型名称").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.app.cloud_model_var, width=46).grid(row=2, column=1, sticky="we", padx=8, pady=6)

        ttk.Label(frame, text="请求超时(秒)").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.app.cloud_timeout_var, width=10).grid(row=3, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(frame, text="留空或 0 表示不限时", foreground="#4b5563").grid(row=4, column=1, sticky="w", padx=8, pady=(0, 6))

        frame.grid_columnconfigure(1, weight=1)

    def _refresh_model_provider_ui(self) -> None:
        if self.local_frame is None or self.cloud_frame is None:
            return

        if self.app.provider_var.get() == "local":
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
