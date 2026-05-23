import csv
import datetime
import os
import time
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk, messagebox
import threading
from pathlib import Path
from typing import TypedDict

from config_manager import ConfigManager
from text_utils import parse_timeout
from translator_gateway import TranslatorGateway
from ui_pages import (
    ModelConfigDialog,
    open_prompt_config_window,
    open_system_config_window,
    open_terminology_config_window,
)


class TranslationRuntimeConfig(TypedDict):
    provider: str
    ollama_host: str
    ollama_model: str
    ollama_timeout: float | None
    cloud_base_url: str
    cloud_api_key: str
    cloud_model: str
    cloud_timeout: float | None


class TranslatorUI:
    def _get_log_file(self) -> str:
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return os.path.join(log_dir, f"trans_{now}.log")
    def _open_system_config_window(self) -> None:
        open_system_config_window(self)

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
        widget_names = [
            "input_text",
            "reference_text",
            "output_text",
            "prompt_text_widget",
        ]
        for widget_name in widget_names:
            widget = getattr(self, widget_name, None)
            if widget is None:
                continue
            try:
                if widget.winfo_exists():
                    widget.config(font=self.default_font)
            except tk.TclError:
                continue

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Wiki 翻译工具")
        self.root.geometry("1000x620")
        self.root.minsize(900, 560)
        self.config_path = Path(__file__).with_name("translator_config.json")
        self.terminology_template_path = self.config_path.with_name("terminology_template.tsv")
        self.config_manager = ConfigManager(self.config_path)

        self.input_chunks: list[str] = []
        self.current_index = 0
        self.output_buffer: list[str] = []
        self.active_chunk_text = ""
        self.current_prompt = ""
        self.current_terminology_path = ""
        self.current_terminology_entries: list[dict[str, str]] = []
        self.current_reference_text = ""
        self.current_runtime_config: TranslationRuntimeConfig | None = None
        self.translation_started_at: float | None = None
        self.translation_status_job: str | None = None
        self.translation_status_tick = 0
        self.translation_error_count = 0

        self.provider_var = tk.StringVar(value="local")
        self.local_provider_var = tk.StringVar(value="ollama")
        self.ollama_host_var = tk.StringVar(value="http://127.0.0.1:11434")
        self.ollama_model_var = tk.StringVar(value="qwen2.5:7b")
        self.ollama_timeout_var = tk.StringVar(value="20")

        self.cloud_base_url_var = tk.StringVar(value="https://api.openai.com/v1")
        self.cloud_api_key_var = tk.StringVar(value="")
        self.cloud_model_var = tk.StringVar(value="gpt-4o-mini")
        self.cloud_timeout_var = tk.StringVar(value="20")
        self.terminology_path_var = tk.StringVar(value="")
        self.test_status_var = tk.StringVar(value="")

        self.model_config_window: tk.Toplevel | None = None
        self.local_frame: ttk.Frame | None = None
        self.cloud_frame: ttk.Frame | None = None
        self.test_button: ttk.Button | None = None
        self.inference_test_button: ttk.Button | None = None
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
        config_menu.add_command(label="术语配置", command=self._open_terminology_config_window)
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
        open_prompt_config_window(self)

    def _open_terminology_config_window(self) -> None:
        open_terminology_config_window(self)

    def _save_prompt_to_config(self, prompt: str) -> None:
        config_data = self._collect_config()
        config_data["prompt"] = prompt
        self.config_manager.save(config_data)

    def _save_terminology_to_config(self, terminology_path: str) -> None:
        config_data = self._collect_config()
        config_data["terminology_path"] = terminology_path.strip()
        config_data.pop("terminology", None)
        self.config_manager.save(config_data)

    def _create_scrollable_text(self, parent: ttk.LabelFrame, **text_options) -> tk.Text:
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True, padx=8, pady=8)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        text_widget = tk.Text(container, **text_options)
        text_widget.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=text_widget.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        text_widget.configure(yscrollcommand=scrollbar.set)
        return text_widget

    # ...existing code...


    def _build_main_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        text_panel = ttk.Frame(outer)
        text_panel.pack(fill="both", expand=True)

        # 三栏布局：原文输入、参考文本、翻译结果

        text_panel.grid_rowconfigure(0, weight=1)
        text_panel.grid_columnconfigure(0, weight=1)
        text_panel.grid_columnconfigure(1, weight=1)
        text_panel.grid_columnconfigure(2, weight=1)

        left_frame = ttk.LabelFrame(text_panel, text="原文输入")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)

        ref_frame = ttk.LabelFrame(text_panel, text="参考文本")
        ref_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=0)

        right_frame = ttk.LabelFrame(text_panel, text="翻译结果")
        right_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 0), pady=0)

        self.input_text = self._create_scrollable_text(
            left_frame,
            wrap="word",
            font=self.default_font,
            undo=True,
        )

        self.reference_text = self._create_scrollable_text(
            ref_frame,
            wrap="word",
            font=self.default_font,
            undo=True,
        )

        self.output_text = self._create_scrollable_text(
            right_frame,
            wrap="word",
            font=self.default_font,
            state="disabled",
        )

        self.input_text.bind("<Control-a>", self._select_all_text)
        self.input_text.bind("<Control-A>", self._select_all_text)
        self.reference_text.bind("<Control-a>", self._select_all_text)
        self.reference_text.bind("<Control-A>", self._select_all_text)
        self.output_text.bind("<Control-a>", self._select_all_text)
        self.output_text.bind("<Control-A>", self._select_all_text)

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
        self._log_file = self._get_log_file()
        raw_text = self.input_text.get("1.0", "end-1c").strip()
        if not raw_text:
            messagebox.showwarning("提示", "请先粘贴待翻译文本。")
            return

        config_data = self.config_manager.read_merged()
        self.current_prompt = str(config_data.get("prompt", "")).strip()
        self.current_terminology_path = str(config_data.get("terminology_path", "")).strip()
        self.current_terminology_entries = []
        if self.current_terminology_path:
            try:
                self.current_terminology_entries = self._load_terminology_entries(self.current_terminology_path)
            except FileNotFoundError:
                self.current_terminology_entries = []
            except (OSError, ValueError) as exc:
                messagebox.showwarning("提示", f"术语表加载失败: {exc}")
                return
        # 参考文本直接取界面输入
        self.current_reference_text = self.reference_text.get("1.0", "end-1c").strip()

        try:
            self.current_runtime_config = self._collect_runtime_config()
        except ValueError as exc:
            messagebox.showwarning("提示", f"翻译配置无效: {exc}")
            return

        self.input_chunks = [raw_text]
        self.current_index = 0
        self.output_buffer = []
        self.active_chunk_text = ""
        self.translation_started_at = time.monotonic()
        self.translation_status_tick = 0
        self.translation_error_count = 0
        self.progress_var.set(0)
        self._set_output_text(self._build_waiting_output_hint())
        self._start_translation_feedback()

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
        self.active_chunk_text = ""
        self.status_var.set(f"翻译中... {self.current_index + 1}/{len(self.input_chunks)}")
        threading.Thread(target=self._translate_current_chunk, args=(chunk,), daemon=True).start()

    def _translate_current_chunk(self, chunk: str) -> None:
        error_message = None
        try:
            translated = self._real_translate(chunk, self._schedule_stream_chunk)
        except Exception as exc:
            translated = self._format_translation_error(chunk, exc)
            error_message = str(exc).strip() or exc.__class__.__name__

        self.root.after(0, self._finish_translate_chunk, translated, error_message)

    def _schedule_stream_chunk(self, chunk: str) -> None:
        self.root.after(0, self._append_stream_output, chunk)

    def _append_stream_output(self, chunk: str) -> None:
        self.active_chunk_text += chunk
        display_parts = self.output_buffer.copy()
        if self.active_chunk_text:
            display_parts.append(self.active_chunk_text)
        self._set_output_text("\n".join(display_parts))

    def _finish_translate_chunk(self, translated: str, error_message: str | None = None) -> None:
        self.output_buffer.append(translated)
        self.active_chunk_text = ""
        self._set_output_text("\n".join(self.output_buffer))

        if error_message:
            self.translation_error_count += 1

        self.current_index += 1
        if self.progress.cget("mode") == "determinate":
            progress = (self.current_index / len(self.input_chunks)) * 100
            self.progress_var.set(progress)

        if self.current_index >= len(self.input_chunks):
            self._stop_translation_feedback()
            self.start_button.config(state="normal")
            self.progress.configure(mode="determinate")
            self.progress_var.set(100 if self.translation_error_count == 0 else 0)
            if self.translation_error_count:
                self.status_var.set(f"翻译结束，含 {self.translation_error_count} 个错误")
            else:
                self.status_var.set("翻译完成")
            return

        self.status_var.set(f"翻译中... {self.current_index}/{len(self.input_chunks)}")
        self.root.after(80, self._translate_step)

    def _build_waiting_output_hint(self) -> str:
        runtime_config = self.current_runtime_config or {}
        provider = str(runtime_config.get("provider", ""))
        if provider == "local":
            model = str(runtime_config.get("ollama_model", "")).strip()
            timeout = runtime_config.get("ollama_timeout")
        else:
            model = str(runtime_config.get("cloud_model", "")).strip()
            timeout = runtime_config.get("cloud_timeout")

        timeout_text = "不限时" if timeout is None else f"{timeout:g} 秒"
        parts = ["[系统运行中] 已发送完整请求，正在等待模型返回首个输出片段。"]
        if model:
            parts.append(f"当前模型: {model}。")
        parts.append(f"超时设置: {timeout_text}。")
        parts.append("长文本或首次加载模型时，等待时间可能较长。")
        return " ".join(parts)

    def _start_translation_feedback(self) -> None:
        self._stop_translation_feedback()
        self.progress.configure(mode="indeterminate")
        self.progress.start(10)
        self._schedule_translation_feedback()

    def _stop_translation_feedback(self) -> None:
        if self.translation_status_job is not None:
            self.root.after_cancel(self.translation_status_job)
            self.translation_status_job = None
        self.progress.stop()

    def _schedule_translation_feedback(self) -> None:
        total_chunks = len(self.input_chunks)
        if total_chunks == 0:
            return

        chunk_label = f"{min(self.current_index + 1, total_chunks)}/{total_chunks}"
        elapsed = 0.0 if self.translation_started_at is None else time.monotonic() - self.translation_started_at
        dots = "." * ((self.translation_status_tick % 3) + 1)
        phase = "等待模型响应" if not self.active_chunk_text else "正在接收输出"
        self.status_var.set(f"翻译中{dots} 第 {chunk_label} 段，{phase}，已运行 {elapsed:.0f} 秒")
        self.translation_status_tick += 1
        self.translation_status_job = self.root.after(700, self._schedule_translation_feedback)

    @staticmethod
    def _is_timeout_exception(exc: Exception) -> bool:
        if isinstance(exc, TimeoutError):
            return True
        message = str(exc).casefold()
        return "timed out" in message or "请求超时" in message

    def _format_translation_error(self, chunk: str, exc: Exception) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        if not self._is_timeout_exception(exc):
            return f"[翻译出错: {message}]"

        runtime_config = self.current_runtime_config or {}
        provider = str(runtime_config.get("provider", ""))
        if provider == "local":
            model = str(runtime_config.get("ollama_model", "")).strip()
            timeout = runtime_config.get("ollama_timeout")
        else:
            model = str(runtime_config.get("cloud_model", "")).strip()
            timeout = runtime_config.get("cloud_timeout")

        metadata = [f"当前请求约 {len(self._compose_translation_input(chunk))} 字符"]
        if model:
            metadata.append(f"模型 {model}")
        if isinstance(timeout, (int, float)):
            metadata.append(f"超时设置 {timeout:g} 秒")
        else:
            metadata.append("超时设置 不限时")

        return (
            f"[翻译超时: {message} {'，'.join(metadata)}。"
            "请缩短待翻译/参考文本、提高超时，或改用更快的模型。]"
        )

    def _real_translate(self, chunk: str, on_chunk: Callable[[str], None] | None = None) -> str:
        runtime_config = self.current_runtime_config
        if runtime_config is None:
            raise RuntimeError("翻译配置未初始化")

        provider = runtime_config["provider"]
        full_prompt = self._compose_translation_input(chunk)
        llm_output = ""
        request_error: Exception | None = None
        try:
            if provider == "local":
                if on_chunk is None:
                    llm_output = TranslatorGateway.translate_ollama(
                        runtime_config["ollama_host"],
                        runtime_config["ollama_model"],
                        full_prompt,
                        runtime_config["ollama_timeout"],
                    )
                else:
                    llm_output = TranslatorGateway.translate_ollama_stream(
                        runtime_config["ollama_host"],
                        runtime_config["ollama_model"],
                        full_prompt,
                        on_chunk,
                        runtime_config["ollama_timeout"],
                    )
            else:
                llm_output = TranslatorGateway.translate_cloud(
                    runtime_config["cloud_base_url"],
                    runtime_config["cloud_api_key"],
                    runtime_config["cloud_model"],
                    full_prompt,
                    runtime_config["cloud_timeout"],
                )
        except Exception as exc:
            request_error = exc
            raise
        finally:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write("===== REQUEST META =====\n")
                    f.write(f"provider={provider}\n")
                    f.write(f"prompt_chars={len(full_prompt)}\n")
                    f.write(f"reference_chars={len(self.current_reference_text)}\n")
                    f.write(f"chunk_chars={len(chunk)}\n")
                    if provider == "local":
                        f.write(f"model={runtime_config['ollama_model']}\n")
                        f.write(f"timeout={runtime_config['ollama_timeout']}\n")
                    else:
                        f.write(f"model={runtime_config['cloud_model']}\n")
                        f.write(f"timeout={runtime_config['cloud_timeout']}\n")
                    if request_error is not None:
                        f.write("\n===== REQUEST ERROR =====\n")
                        f.write(repr(request_error))
                        f.write("\n")
                    f.write("\n")
                    f.write("===== PROMPT SENT TO LLM =====\n")
                    f.write(full_prompt)
                    f.write("\n\n===== LLM RAW OUTPUT =====\n")
                    f.write(str(llm_output))
                    f.write("\n\n===========================\n")
            except Exception as log_exc:
                print(f"[Log Write Error]: {log_exc}")
        return llm_output

    def _collect_runtime_config(self) -> TranslationRuntimeConfig:
        provider = self.provider_var.get()
        return {
            "provider": provider,
            "ollama_host": self.ollama_host_var.get(),
            "ollama_model": self.ollama_model_var.get(),
            "ollama_timeout": parse_timeout(self.ollama_timeout_var.get()) if provider == "local" else None,
            "cloud_base_url": self.cloud_base_url_var.get(),
            "cloud_api_key": self.cloud_api_key_var.get(),
            "cloud_model": self.cloud_model_var.get(),
            "cloud_timeout": parse_timeout(self.cloud_timeout_var.get()) if provider != "local" else None,
        }

    def _compose_translation_input(self, chunk: str) -> str:
        sections: list[str] = []
        if self.current_prompt:
            sections.append(f"【翻译要求】\n{self.current_prompt}")
        terminology_block = self._build_terminology_block(chunk)
        if terminology_block:
            sections.append(f"【术语要求】\n{terminology_block}")
        if self.current_reference_text:
            sections.append(f"【参考文本】\n{self.current_reference_text}")
        sections.append(f"【待翻译文本】\n{chunk}")
        return "\n\n".join(sections)

    def _build_terminology_block(self, chunk: str) -> str:
        if not self.current_terminology_entries:
            return ""

        chunk_text = chunk.casefold()
        matched_entries = [
            entry for entry in self.current_terminology_entries if entry["source"].casefold() in chunk_text
        ]
        if not matched_entries:
            return ""

        matched_entries.sort(key=lambda entry: len(entry["source"]), reverse=True)
        lines = ["请优先使用以下术语对照:"]
        for entry in matched_entries:
            item = f"- {entry['source']} -> {entry['target']}"
            if entry["note"]:
                item += f" ({entry['note']})"
            lines.append(item)
        return "\n".join(lines)

    def _load_terminology_entries(self, terminology_path: str) -> list[dict[str, str]]:
        normalized_path = terminology_path.strip()
        if not normalized_path:
            return []

        glossary_path = self._resolve_terminology_path(normalized_path)
        if not glossary_path.exists():
            raise FileNotFoundError(f"未找到术语表文件: {glossary_path}")
        if not glossary_path.is_file():
            raise ValueError(f"术语表路径不是文件: {glossary_path}")

        entries: list[dict[str, str]] = []
        with glossary_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t")
            for line_number, row in enumerate(reader, start=1):
                normalized_row = [column.strip() for column in row]
                if not normalized_row or not any(normalized_row):
                    continue
                if normalized_row[0].startswith("#"):
                    continue
                if self._is_terminology_header(normalized_row):
                    continue
                if len(normalized_row) < 2 or not normalized_row[0] or not normalized_row[1]:
                    raise ValueError(
                        f"{glossary_path.name} 第 {line_number} 行格式无效，应为 source_term[TAB]target_term[TAB]note"
                    )

                entries.append({
                    "source": normalized_row[0],
                    "target": normalized_row[1],
                    "note": normalized_row[2] if len(normalized_row) > 2 else "",
                })
        return entries

    def _resolve_terminology_path(self, terminology_path: str) -> Path:
        candidate = Path(terminology_path).expanduser()
        if not candidate.is_absolute():
            candidate = self.config_path.parent / candidate
        return candidate

    @staticmethod
    def _is_terminology_header(row: list[str]) -> bool:
        if len(row) < 2:
            return False
        first_column = row[0].casefold()
        second_column = row[1].casefold()
        source_markers = {"source", "source_term", "term", "source phrase"}
        target_markers = {"target", "target_term", "translation", "target phrase"}
        return first_column in source_markers and second_column in target_markers

    def _open_model_config_window(self) -> None:
        ModelConfigDialog(self).open()

    def _load_or_create_config(self) -> None:
        config_data = self.config_manager.load_or_create()
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
        self.config_manager.save(config_data)

    def _collect_config(self) -> dict:
        # 读取现有配置，保留 prompt 等非表单字段，并补齐默认值
        config_data = self.config_manager.read_merged()
        config_data.update({
            "provider": self.provider_var.get(),
            "local_provider": self.local_provider_var.get(),
            "system": {
                "font_family": self.font_family_var.get(),
                "font_size": self.font_size_var.get(),
            },
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
            "terminology_path": self.terminology_path_var.get().strip(),
        })
        config_data.pop("terminology", None)
        return config_data

    def _apply_config(self, config_data: dict) -> None:
        defaults = self.config_manager.default_config()
        merged = {
            **defaults,
            **config_data,
            "system": {**defaults["system"], **config_data.get("system", {})},
            "ollama": {**defaults["ollama"], **config_data.get("ollama", {})},
            "cloud": {**defaults["cloud"], **config_data.get("cloud", {})},
        }

        font_family = str(merged["system"].get("font_family", self.default_font[0]))
        try:
            font_size = int(merged["system"].get("font_size", self.default_font[1]))
        except (TypeError, ValueError):
            font_size = int(self.default_font[1])

        self.font_family_var.set(font_family)
        self.font_size_var.set(font_size)
        self.default_font = (font_family, font_size)

        self.provider_var.set(str(merged.get("provider", "local")))
        self.local_provider_var.set(str(merged.get("local_provider", "ollama")))
        self.ollama_host_var.set(str(merged["ollama"].get("host", "http://127.0.0.1:11434")))
        self.ollama_model_var.set(str(merged["ollama"].get("model", "qwen2.5:7b")))
        self.ollama_timeout_var.set(str(merged["ollama"].get("timeout", "20")))
        self.cloud_base_url_var.set(str(merged["cloud"].get("base_url", "https://api.openai.com/v1")))
        self.cloud_api_key_var.set(str(merged["cloud"].get("api_key", "")))
        self.cloud_model_var.set(str(merged["cloud"].get("model", "gpt-4o-mini")))
        self.cloud_timeout_var.set(str(merged["cloud"].get("timeout", "20")))
        self.terminology_path_var.set(str(merged.get("terminology_path", "")).strip())

    @staticmethod
    def _default_config() -> dict:
        return ConfigManager.default_config()

    def _set_model_test_buttons_state(self, state: str) -> None:
        if self.test_button is not None:
            self.test_button.config(state=state)
        if self.inference_test_button is not None:
            self.inference_test_button.config(state=state)

    def _start_model_test(self) -> None:
        self._set_model_test_buttons_state("disabled")
        self.test_status_var.set("测试连接中，请稍候...")
        threading.Thread(target=self._run_model_test, args=(False,), daemon=True).start()

    def _start_model_inference_test(self) -> None:
        self._set_model_test_buttons_state("disabled")
        self.test_status_var.set("测试推理中，请稍候...")
        threading.Thread(target=self._run_model_test, args=(True,), daemon=True).start()

    def _run_model_test(self, inference: bool) -> None:
        try:
            if self.provider_var.get() == "local":
                result = self._test_ollama_inference() if inference else self._test_ollama_connection()
            else:
                result = self._test_cloud_inference() if inference else self._test_cloud_connection()
            self.root.after(0, self._finish_model_test, True, result)
        except Exception as exc:
            label = "推理测试失败" if inference else "连接测试失败"
            self.root.after(0, self._finish_model_test, False, f"{label}: {exc}")

    def _finish_model_test(self, success: bool, text: str) -> None:
        self.test_status_var.set(text)
        self._set_model_test_buttons_state("normal")

        if self.status_label_widget is not None:
            self.status_label_widget.config(foreground="#0f5132" if success else "#842029")

    def _test_ollama_connection(self) -> str:
        host = self.ollama_host_var.get()
        model = self.ollama_model_var.get()
        timeout = parse_timeout(self.ollama_timeout_var.get())
        return TranslatorGateway.test_ollama_connection(host, model, timeout)

    def _test_ollama_inference(self) -> str:
        host = self.ollama_host_var.get()
        model = self.ollama_model_var.get()
        timeout = parse_timeout(self.ollama_timeout_var.get())
        return TranslatorGateway.test_ollama_inference(host, model, timeout)

    def _test_cloud_connection(self) -> str:
        base_url = self.cloud_base_url_var.get()
        api_key = self.cloud_api_key_var.get()
        model = self.cloud_model_var.get()
        timeout = parse_timeout(self.cloud_timeout_var.get())
        return TranslatorGateway.test_cloud_connection(base_url, api_key, model, timeout)

    def _test_cloud_inference(self) -> str:
        base_url = self.cloud_base_url_var.get()
        api_key = self.cloud_api_key_var.get()
        model = self.cloud_model_var.get()
        timeout = parse_timeout(self.cloud_timeout_var.get())
        return TranslatorGateway.test_cloud_inference(base_url, api_key, model, timeout)

    def _on_model_window_close(self) -> None:
        self._save_config_file()
        if self.model_config_window is not None and self.model_config_window.winfo_exists():
            self.model_config_window.destroy()
        self.model_config_window = None

    @staticmethod
    def _mock_translate(chunk: str) -> str:
        # 预留真实翻译调用位置：后续可替换为本地LLM接口。
        return chunk

    def _set_output_text(self, content: str) -> None:
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", content)
        self.output_text.see("end")
        self.output_text.config(state="disabled")

    @staticmethod
    def _select_all_text(event: tk.Event) -> str:
        widget = event.widget
        if isinstance(widget, tk.Text):
            current_state = widget.cget("state")
            if current_state == "disabled":
                widget.config(state="normal")
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
            widget.see("insert")
            if current_state == "disabled":
                widget.config(state="disabled")
        elif isinstance(widget, (tk.Entry, ttk.Entry)):
            widget.selection_range(0, "end")
            widget.icursor(0)
        return "break"

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
