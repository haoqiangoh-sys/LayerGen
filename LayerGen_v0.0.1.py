# -*- coding: utf-8 -*-
"""
LayerGen

A lightweight tool for prompt engineering and model stacking.

Run with:
    python LayerGen.py
"""

import json
import os
import queue
import threading
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk


APP_TITLE = "LayerGen"
SESSION_VERSION = 4
ANTHROPIC_VERSION = "2023-06-01"

PROVIDERS = ("Gemini", "OpenAI-compatible", "Anthropic")
DEFAULT_BASE_URLS = {
    "Gemini": "https://generativelanguage.googleapis.com/v1beta",
    "OpenAI-compatible": "https://api.openai.com/v1",
    "Anthropic": "https://api.anthropic.com/v1",
}
PROVIDER_ENV_KEYS = {
    "Gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "OpenAI-compatible": ("OPENAI_API_KEY", "API_KEY"),
    "Anthropic": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
}
KEY_SCOPES = ("Shared provider key", "Layer-specific key")
CHAT_MODES = ("Replace outputs", "Append outputs")

LANGUAGE_EXTENSIONS = {
    "Plain text": ".txt",
    "Python": ".py",
    "JavaScript": ".js",
    "TypeScript": ".ts",
    "HTML": ".html",
    "CSS": ".css",
    "Java": ".java",
    "C#": ".cs",
    "C++": ".cpp",
    "Go": ".go",
    "Rust": ".rs",
    "Swift": ".swift",
    "Kotlin": ".kt",
    "PHP": ".php",
    "Ruby": ".rb",
    "SQL": ".sql",
    "Markdown": ".md",
    "JSON": ".json",
}

VARIABLES = (
    ("Input", "{input}"),
    ("Language", "{language}"),
    ("Layer name", "{layer_name}"),
    ("Previous output", "{previous_output}"),
    ("All previous outputs", "{all_previous_outputs}"),
    ("Current output", "{current_output}"),
    ("Chat message", "{chat_message}"),
    ("Chat history", "{chat_history}"),
)


def now_label():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_id():
    return uuid.uuid4().hex[:12]


def normalize_base_url(base_url):
    return base_url.strip().rstrip("/")


def join_url(base_url, path):
    return normalize_base_url(base_url) + "/" + path.lstrip("/")


def model_sort_key(model_name):
    lowered = model_name.lower()
    preferred_markers = (
        "claude-sonnet",
        "claude-opus",
        "claude-haiku",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gpt-5",
        "gpt-4.1",
        "gpt-4o",
        "flash",
        "mini",
    )
    for index, marker in enumerate(preferred_markers):
        if marker in lowered:
            return (index, lowered)
    return (len(preferred_markers), lowered)


def clean_error(text):
    if not text:
        return "No error details returned."
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:900]

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            return error.get("message") or json.dumps(error)
        if isinstance(error, str):
            return error
    return json.dumps(data)[:900]


def request_json(url, method="GET", headers=None, payload=None, timeout=180):
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Request failed with HTTP {exc.code}: {clean_error(details)}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network request failed: {exc.reason}")

    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError("The provider returned a response that was not valid JSON.")


def extract_text_from_gemini_response(data):
    parts = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text)
    if parts:
        return "\n".join(parts).strip()

    feedback = data.get("promptFeedback") or data.get("prompt_feedback")
    if feedback:
        raise RuntimeError("Gemini did not return text. Feedback: " + json.dumps(feedback))
    raise RuntimeError("Gemini did not return text.")


def extract_text_from_openai_response(data):
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("The provider response did not include any choices.")

    first = choices[0]
    message = first.get("message", {})
    content = message.get("content")

    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts).strip()
    if first.get("text"):
        return first["text"].strip()

    raise RuntimeError("The provider response did not include text content.")


def extract_text_from_anthropic_response(data):
    parts = []
    for item in data.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
            parts.append(item["text"])
    if parts:
        return "\n".join(parts).strip()
    raise RuntimeError("Anthropic did not return text content.")


def strip_code_fences(text):
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def default_api_key(provider):
    for env_name in PROVIDER_ENV_KEYS.get(provider, ()):
        value = os.environ.get(env_name)
        if value:
            return value.strip()
    return ""


def extract_api_key_from_text(text, provider):
    cleaned = text.strip()
    if not cleaned:
        return ""

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            for key in ("api_key", "apikey", "key", "token"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    except json.JSONDecodeError:
        pass

    expected_names = {name.upper() for name in PROVIDER_ENV_KEYS.get(provider, ())}
    expected_names.update({"API_KEY", "TOKEN", "BEARER_TOKEN"})

    for line in cleaned.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().upper()
        if name in expected_names or name.endswith("_API_KEY"):
            return value.strip().strip('"').strip("'")

    for line in cleaned.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def render_template(template, values):
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def format_chat_history(chat_history, limit=30):
    recent = chat_history[-limit:]
    lines = []
    for item in recent:
        role = "User" if item.get("role") == "user" else "LayerGen"
        layer_name = item.get("layer_name", "")
        stamp = item.get("time", "")
        content = item.get("content", "").strip()
        if content:
            prefix = f"{role}"
            if layer_name:
                prefix += f" [{layer_name}]"
            if stamp:
                prefix += f" {stamp}"
            lines.append(prefix + ":\n" + content)
    return "\n\n".join(lines) if lines else "(No chat history yet.)"


def format_previous_outputs(layers, stop_index):
    blocks = []
    for index in range(stop_index):
        output = layers[index].get("output", "").strip()
        if output:
            blocks.append(f"Layer {index + 1}: {layers[index]['name']}\n{output}")
    return "\n\n".join(blocks)


def append_block(existing, block):
    existing = existing.strip()
    block = block.strip()
    if not existing:
        return block
    if not block:
        return existing
    return existing + "\n\n" + block


def make_addendum_block(layer_name, content):
    return "\n\n" + "=" * 72 + f"\nChat addendum: {layer_name} - {now_label()}\n" + "=" * 72 + "\n" + content.strip()


def build_layer_values(global_input, layers, index, chat_message="", chat_history=""):
    previous_output = ""
    if index > 0:
        previous_output = layers[index - 1].get("output", "")

    layer = layers[index]
    values = {
        "input": global_input,
        "language": layer.get("language", ""),
        "layer_name": layer.get("name", ""),
        "previous_output": previous_output,
        "all_previous_outputs": format_previous_outputs(layers, index),
        "current_output": layer.get("output", ""),
        "chat_message": chat_message,
        "chat_history": chat_history,
    }
    for layer_index, source_layer in enumerate(layers, start=1):
        values[f"layer_{layer_index}_output"] = source_layer.get("output", "")
    return values


def build_chat_prompt(global_input, layers, index, chat_message, chat_history, mode):
    layer = layers[index]
    values = build_layer_values(
        global_input,
        layers,
        index,
        chat_message=chat_message,
        chat_history=format_chat_history(chat_history),
    )
    rendered_layer_prompt = render_template(layer.get("prompt", ""), values).strip()

    if mode == "Append outputs":
        instruction = (
            "Return only new material that should be appended to this layer's existing output. "
            "Do not rewrite the whole layer output."
        )
        response_label = "Layer addendum"
    else:
        instruction = (
            "Return one complete updated output for this layer. "
            "Use the existing output as memory, but make the result clean and directly usable."
        )
        response_label = "Complete updated layer output"

    return f"""You are fine-tuning one layer inside LayerGen, a chained multi-layer coding tool.
The user is chatting with this layer specifically. Do not restart earlier layers.
Use the existing layer output, previous layer outputs, and chat history as memory.
{instruction}

Layer name:
{layer.get('name', '')}

Target language:
{layer.get('language', '')}

Configured layer prompt:
{rendered_layer_prompt if rendered_layer_prompt else "(This layer has no configured prompt.)"}

Original user input:
{global_input}

Previous layer output:
{values['previous_output'] if values['previous_output'] else "(No previous layer output.)"}

All earlier layer outputs:
{values['all_previous_outputs'] if values['all_previous_outputs'] else "(No earlier layer outputs.)"}

Current output for this layer:
{layer.get('output', '') if layer.get('output', '').strip() else "(This layer has no output yet.)"}

Chat history:
{values['chat_history']}

User's new message:
{chat_message}

{response_label}:"""


class ProviderClient:
    def __init__(self, provider, api_key, base_url, temperature, max_tokens):
        self.provider = provider
        self.api_key = api_key.strip()
        self.base_url = normalize_base_url(base_url)
        self.temperature = temperature
        self.max_tokens = max_tokens

        if self.provider not in PROVIDERS:
            raise ValueError("Choose a supported provider.")
        if not self.api_key:
            raise ValueError("Enter or load an API key.")
        if not self.base_url:
            raise ValueError("Enter a base URL.")

    def list_models(self):
        if self.provider == "Gemini":
            return self._list_gemini_models()
        if self.provider == "Anthropic":
            return self._list_anthropic_models()
        return self._list_openai_compatible_models()

    def generate(self, model_name, prompt):
        model_name = model_name.strip()
        if not model_name:
            raise ValueError("Choose a model.")

        if self.provider == "Gemini":
            return self._generate_gemini(model_name, prompt)
        if self.provider == "Anthropic":
            return self._generate_anthropic(model_name, prompt)
        return self._generate_openai_compatible(model_name, prompt)

    def _list_gemini_models(self):
        params = urllib.parse.urlencode({"key": self.api_key})
        data = request_json(join_url(self.base_url, "models") + "?" + params)
        model_names = []
        for model in data.get("models", []):
            methods = model.get("supportedGenerationMethods", [])
            if "generateContent" in methods and model.get("name"):
                model_names.append(model["name"])
        return sorted(set(model_names), key=model_sort_key)

    def _generate_gemini(self, model_name, prompt):
        model_path = urllib.parse.quote(model_name, safe="/")
        params = urllib.parse.urlencode({"key": self.api_key})
        url = join_url(self.base_url, model_path + ":generateContent") + "?" + params
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }
        return extract_text_from_gemini_response(
            request_json(url, method="POST", payload=payload)
        )

    def _list_openai_compatible_models(self):
        headers = {"Authorization": "Bearer " + self.api_key}
        data = request_json(join_url(self.base_url, "models"), headers=headers)
        model_names = []
        for model in data.get("data", []):
            if isinstance(model, dict) and model.get("id"):
                model_names.append(model["id"])
        return sorted(set(model_names), key=model_sort_key)

    def _generate_openai_compatible(self, model_name, prompt):
        headers = {"Authorization": "Bearer " + self.api_key}
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        return extract_text_from_openai_response(
            request_json(
                join_url(self.base_url, "chat/completions"),
                method="POST",
                headers=headers,
                payload=payload,
            )
        )

    def _list_anthropic_models(self):
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        models = []
        after_id = None
        while True:
            params = {"limit": "1000"}
            if after_id:
                params["after_id"] = after_id
            url = join_url(self.base_url, "models") + "?" + urllib.parse.urlencode(params)
            data = request_json(url, headers=headers)
            for model in data.get("data", []):
                if isinstance(model, dict) and model.get("id"):
                    models.append(model["id"])
            if not data.get("has_more") or not data.get("last_id"):
                break
            after_id = data["last_id"]
        return sorted(set(models), key=model_sort_key)

    def _generate_anthropic(self, model_name, prompt):
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        payload = {
            "model": model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        return extract_text_from_anthropic_response(
            request_json(
                join_url(self.base_url, "messages"),
                method="POST",
                headers=headers,
                payload=payload,
            )
        )


class LayerPanel:
    def __init__(self, app, data=None):
        self.app = app
        self.id = (data or {}).get("id") or make_id()
        self.frame = ttk.Frame(app.layers_notebook, padding=8)
        self.model_options = list((data or {}).get("model_options", []))

        self.name_var = tk.StringVar(value=(data or {}).get("name", "Layer"))
        self.provider_var = tk.StringVar(value=(data or {}).get("provider", "Gemini"))
        self.base_url_var = tk.StringVar(
            value=(data or {}).get("base_url")
            or DEFAULT_BASE_URLS.get(self.provider_var.get(), "")
        )
        self.key_scope_var = tk.StringVar(
            value=(data or {}).get("key_scope", "Shared provider key")
        )
        self.api_key_var = tk.StringVar(value=(data or {}).get("api_key", ""))
        self.model_var = tk.StringVar(value=(data or {}).get("model", ""))
        self.temperature_var = tk.StringVar(value=str((data or {}).get("temperature", 0.4)))
        self.max_tokens_var = tk.StringVar(value=str((data or {}).get("max_tokens", 4096)))
        self.language_var = tk.StringVar(value=(data or {}).get("language", "Python"))
        self.variable_var = tk.StringVar(value=VARIABLES[0][0])

        self._build_ui()
        self.prompt_text.insert("1.0", (data or {}).get("prompt", ""))
        self.output_text.insert("1.0", (data or {}).get("output", ""))
        self.model_combo.configure(values=self.model_options)
        self._sync_key_from_scope()
        self.refresh_settings_summary()

    def _build_ui(self):
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=2)
        self.frame.rowconfigure(2, weight=3)

        config = ttk.LabelFrame(self.frame, text="Layer", padding=8)
        config.grid(row=0, column=0, sticky="ew")
        for column in range(8):
            config.columnconfigure(column, weight=1)

        self.settings_button = ttk.Menubutton(config, text="Settings")
        self.settings_menu = tk.Menu(self.settings_button, tearoff=0)
        self.settings_button.configure(menu=self.settings_menu)
        self._build_settings_menu()
        self.settings_button.grid(row=0, column=0, sticky="w", padx=(0, 12))

        ttk.Label(config, text="Provider").grid(row=0, column=1, sticky="w")
        provider_combo = ttk.Combobox(
            config,
            textvariable=self.provider_var,
            values=PROVIDERS,
            state="readonly",
        )
        provider_combo.grid(row=0, column=2, sticky="ew", padx=(6, 12))
        provider_combo.bind("<<ComboboxSelected>>", self._provider_changed)

        ttk.Label(config, text="Language").grid(row=0, column=3, sticky="w")
        ttk.Combobox(
            config,
            textvariable=self.language_var,
            values=list(LANGUAGE_EXTENSIONS.keys()),
        ).grid(row=0, column=4, sticky="ew", padx=(6, 12))

        ttk.Label(config, text="Model").grid(row=0, column=5, sticky="w")
        self.model_combo = ttk.Combobox(
            config,
            textvariable=self.model_var,
            values=self.model_options,
            state="readonly",
        )
        self.model_combo.grid(row=0, column=6, sticky="ew", padx=(6, 12))
        ttk.Button(config, text="Load models", command=lambda: self.app.load_models_for_layer(self)).grid(
            row=0, column=7, sticky="ew"
        )

        self.settings_summary_var = tk.StringVar()
        ttk.Label(config, textvariable=self.settings_summary_var, anchor="w").grid(
            row=1, column=0, columnspan=8, sticky="ew", pady=(8, 0)
        )
        self.refresh_settings_summary()

        prompt_frame = ttk.LabelFrame(self.frame, text="Prompt", padding=6)
        prompt_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        prompt_frame.columnconfigure(0, weight=1)
        prompt_frame.rowconfigure(1, weight=1)

        prompt_tools = ttk.Frame(prompt_frame)
        prompt_tools.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(prompt_tools, text="Insert").pack(side="left")
        self.variable_combo = ttk.Combobox(
            prompt_tools,
            textvariable=self.variable_var,
            values=self.app.variable_labels(),
            state="readonly",
            width=20,
        )
        self.variable_combo.pack(side="left", padx=(6, 6))
        ttk.Button(prompt_tools, text="Insert variable", command=self.insert_variable).pack(
            side="left"
        )
        ttk.Button(prompt_tools, text="Clear prompt", command=self.clear_prompt).pack(
            side="right"
        )

        self.prompt_text = tk.Text(prompt_frame, wrap="word", undo=True, height=10)
        prompt_scroll = ttk.Scrollbar(prompt_frame, orient="vertical", command=self.prompt_text.yview)
        self.prompt_text.configure(yscrollcommand=prompt_scroll.set)
        self.prompt_text.grid(row=1, column=0, sticky="nsew")
        prompt_scroll.grid(row=1, column=1, sticky="ns")

        output_frame = ttk.LabelFrame(self.frame, text="Output", padding=6)
        output_frame.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)

        output_tools = ttk.Frame(output_frame)
        output_tools.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(output_tools, text="Copy output", command=self.copy_output).pack(side="left")
        ttk.Button(output_tools, text="Save output", command=self.save_output).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(output_tools, text="Clear output", command=self.clear_output).pack(
            side="right"
        )

        self.output_text = tk.Text(output_frame, wrap="none", undo=True, height=14)
        output_y = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        output_x = ttk.Scrollbar(output_frame, orient="horizontal", command=self.output_text.xview)
        self.output_text.configure(yscrollcommand=output_y.set, xscrollcommand=output_x.set)
        self.output_text.grid(row=1, column=0, sticky="nsew")
        output_y.grid(row=1, column=1, sticky="ns")
        output_x.grid(row=2, column=0, sticky="ew")

    def _build_settings_menu(self):
        self.settings_menu.delete(0, "end")
        self.settings_menu.add_command(label="Layer name...", command=self.edit_layer_name)
        self.settings_menu.add_command(label="Base URL...", command=self.edit_base_url)
        self.settings_menu.add_separator()
        self.settings_menu.add_command(label="Temperature...", command=self.edit_temperature)
        self.settings_menu.add_command(label="Max tokens...", command=self.edit_max_tokens)
        self.settings_menu.add_separator()

        api_menu = tk.Menu(self.settings_menu, tearoff=0)
        api_menu.add_radiobutton(
            label="Use shared provider key",
            variable=self.key_scope_var,
            value="Shared provider key",
            command=self._key_scope_changed,
        )
        api_menu.add_radiobutton(
            label="Use layer-specific key",
            variable=self.key_scope_var,
            value="Layer-specific key",
            command=self._key_scope_changed,
        )
        api_menu.add_separator()
        api_menu.add_command(label="Enter API key...", command=self.enter_api_key)
        api_menu.add_command(label="Load API key from file...", command=self.load_api_key)
        api_menu.add_command(label="Clear API key", command=self.clear_api_key)
        self.settings_menu.add_cascade(label="API key", menu=api_menu)

    def refresh_settings_summary(self):
        if not hasattr(self, "settings_summary_var"):
            return
        key_status = "key set" if self.effective_api_key() else "no key"
        summary = (
            f"{self.display_name()} | "
            f"{self.key_scope_var.get()} ({key_status}) | "
            f"temp {self.temperature_var.get()} | "
            f"max {self.max_tokens_var.get()}"
        )
        self.settings_summary_var.set(summary)

    def edit_layer_name(self):
        name = simpledialog.askstring(
            "Layer name",
            "Layer name:",
            initialvalue=self.display_name(),
            parent=self.app,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        self.name_var.set(name)
        self.app.refresh_layer_titles()
        self.refresh_settings_summary()

    def edit_base_url(self):
        base_url = simpledialog.askstring(
            "Base URL",
            "Base URL:",
            initialvalue=self.base_url_var.get(),
            parent=self.app,
        )
        if base_url is None:
            return
        self.base_url_var.set(base_url.strip())
        self.refresh_settings_summary()

    def edit_temperature(self):
        try:
            initial = float(self.temperature_var.get())
        except ValueError:
            initial = 0.4
        value = simpledialog.askfloat(
            "Temperature",
            "Temperature, 0 to 2:",
            initialvalue=initial,
            minvalue=0.0,
            maxvalue=2.0,
            parent=self.app,
        )
        if value is None:
            return
        self.temperature_var.set(str(value))
        self.refresh_settings_summary()

    def edit_max_tokens(self):
        try:
            initial = int(float(self.max_tokens_var.get()))
        except ValueError:
            initial = 4096
        value = simpledialog.askinteger(
            "Max tokens",
            "Max tokens:",
            initialvalue=initial,
            minvalue=1,
            maxvalue=200000,
            parent=self.app,
        )
        if value is None:
            return
        self.max_tokens_var.set(str(value))
        self.refresh_settings_summary()

    def enter_api_key(self):
        key = simpledialog.askstring(
            "API key",
            "API key:",
            initialvalue=self.api_key_var.get(),
            show="*",
            parent=self.app,
        )
        if key is None:
            return
        self.api_key_var.set(key.strip())
        self._api_key_changed()
        self.refresh_settings_summary()

    def clear_api_key(self):
        self.api_key_var.set("")
        self._api_key_changed()
        self.refresh_settings_summary()

    def _provider_changed(self, event=None):
        provider = self.provider_var.get()
        self.base_url_var.set(DEFAULT_BASE_URLS.get(provider, ""))
        self.model_options = []
        self.model_combo.configure(values=[])
        self.model_var.set("")
        self._sync_key_from_scope()
        self.refresh_settings_summary()
        self.app.refresh_chat_layers()

    def _key_scope_changed(self, event=None):
        self._sync_key_from_scope()
        self.refresh_settings_summary()

    def _api_key_changed(self, event=None):
        if self.key_scope_var.get() == "Shared provider key":
            self.app.set_shared_key(self.provider_var.get(), self.api_key_var.get(), source=self)
        self.refresh_settings_summary()

    def _sync_key_from_scope(self):
        provider = self.provider_var.get()
        if self.key_scope_var.get() == "Shared provider key":
            self.api_key_var.set(self.app.shared_keys.get(provider, ""))

    def set_shared_key_value(self, provider, key):
        if self.provider_var.get() == provider and self.key_scope_var.get() == "Shared provider key":
            self.api_key_var.set(key)

    def insert_variable(self):
        selected = self.variable_var.get()
        token = self.app.variable_token(selected)
        self.prompt_text.insert("insert", token)
        self.prompt_text.focus_set()

    def refresh_variable_options(self):
        labels = self.app.variable_labels()
        self.variable_combo.configure(values=labels)
        if self.variable_var.get() not in labels:
            self.variable_var.set(labels[0])

    def clear_prompt(self):
        self.prompt_text.delete("1.0", "end")

    def clear_output(self):
        self.output_text.delete("1.0", "end")

    def load_api_key(self):
        path = filedialog.askopenfilename(
            title="Load API key",
            filetypes=[
                ("Text, env, and JSON files", "*.txt *.env *.json"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
            key = extract_api_key_from_text(text, self.provider_var.get())
            if not key:
                raise ValueError("No API key was found in that file.")
            self.api_key_var.set(key)
            if self.key_scope_var.get() == "Shared provider key":
                self.app.set_shared_key(self.provider_var.get(), key, source=self)
            self.refresh_settings_summary()
            self.app.log("Loaded API key for " + self.display_name() + ".")
        except Exception as exc:
            messagebox.showerror("Could not load API key", str(exc))

    def display_name(self):
        return self.name_var.get().strip() or "Layer"

    def get_prompt(self):
        return self.prompt_text.get("1.0", "end-1c").strip()

    def get_output(self):
        return self.output_text.get("1.0", "end-1c").strip()

    def set_output(self, value):
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", value)
        self.output_text.see("end")

    def append_output(self, value):
        existing = self.get_output()
        if existing:
            self.output_text.insert("end", "\n\n" + value.strip())
        else:
            self.output_text.insert("end", value.strip())
        self.output_text.see("end")

    def effective_api_key(self):
        provider = self.provider_var.get()
        key = self.api_key_var.get().strip()
        if self.key_scope_var.get() == "Shared provider key":
            if key:
                self.app.shared_keys[provider] = key
            return self.app.shared_keys.get(provider, "").strip()
        return key

    def runtime_state(self):
        provider = self.provider_var.get()
        try:
            temperature = float(self.temperature_var.get().strip())
        except ValueError:
            raise ValueError(self.display_name() + ": temperature must be a number.")
        try:
            max_tokens = int(float(self.max_tokens_var.get().strip()))
        except ValueError:
            raise ValueError(self.display_name() + ": max tokens must be a number.")

        return {
            "id": self.id,
            "name": self.display_name(),
            "provider": provider,
            "base_url": self.base_url_var.get().strip(),
            "api_key": self.effective_api_key(),
            "key_scope": self.key_scope_var.get(),
            "model": self.model_var.get().strip(),
            "model_options": list(self.model_options),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "language": self.language_var.get().strip() or "Plain text",
            "prompt": self.get_prompt(),
            "output": self.get_output(),
        }

    def to_dict(self, save_keys=False):
        state = self.runtime_state()
        if not save_keys:
            state["api_key"] = ""
        return state

    def copy_output(self):
        output = self.get_output()
        if not output:
            messagebox.showinfo("Nothing to copy", "This layer has no output yet.")
            return
        self.app.clipboard_clear()
        self.app.clipboard_append(output)
        self.app.status_var.set("Output copied")

    def save_output(self):
        self.app.save_layer_output(self)


class LayerGenApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x860")
        self.minsize(1040, 700)

        self.events = queue.Queue()
        self.worker = None
        self.layers = []
        self.chat_history = []
        self.session_path = None
        self.shared_keys = {provider: default_api_key(provider) for provider in PROVIDERS}

        self.save_keys_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")
        self.chat_layer_var = tk.StringVar(value="")
        self.chat_mode_var = tk.StringVar(value="Replace outputs")

        self._build_ui()
        self.bind_all("<Control-s>", self.save_session_shortcut)
        self.bind_all("<Control-S>", self.save_session_as_shortcut)
        self.bind_all("<Control-Shift-S>", self.save_session_as_shortcut)
        self.after(100, self._process_events)

    def _build_ui(self):
        self._build_menu_bar()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(self, padding=(10, 10, 10, 4))
        toolbar.grid(row=0, column=0, sticky="ew")

        self.add_layer_button = ttk.Button(toolbar, text="New layer", command=self.add_layer)
        self.add_layer_button.pack(side="left")
        self.duplicate_layer_button = ttk.Button(toolbar, text="Duplicate", command=self.duplicate_layer)
        self.duplicate_layer_button.pack(side="left", padx=(8, 0))
        self.delete_layer_button = ttk.Button(toolbar, text="Delete", command=self.delete_layer)
        self.delete_layer_button.pack(side="left", padx=(8, 0))
        self.left_button = ttk.Button(toolbar, text="Move left", command=lambda: self.move_layer(-1))
        self.left_button.pack(side="left", padx=(8, 0))
        self.right_button = ttk.Button(toolbar, text="Move right", command=lambda: self.move_layer(1))
        self.right_button.pack(side="left", padx=(8, 0))

        self.run_selected_button = ttk.Button(
            toolbar,
            text="Run selected + after",
            command=self.run_selected_and_after,
        )
        self.run_selected_button.pack(side="left", padx=(16, 0))
        self.run_all_button = ttk.Button(toolbar, text="Run all", command=self.run_all)
        self.run_all_button.pack(side="left", padx=(8, 0))

        ttk.Checkbutton(toolbar, text="Save keys", variable=self.save_keys_var).pack(
            side="right"
        )

        input_frame = ttk.LabelFrame(self, text="Input", padding=8)
        input_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        input_frame.columnconfigure(0, weight=1)
        self.input_text = tk.Text(input_frame, wrap="word", height=4, undo=True)
        input_scroll = ttk.Scrollbar(input_frame, orient="vertical", command=self.input_text.yview)
        self.input_text.configure(yscrollcommand=input_scroll.set)
        self.input_text.grid(row=0, column=0, sticky="ew")
        input_scroll.grid(row=0, column=1, sticky="ns")

        main_notebook = ttk.Notebook(self)
        main_notebook.grid(row=2, column=0, sticky="nsew", padx=10)

        layers_frame = ttk.Frame(main_notebook, padding=4)
        layers_frame.columnconfigure(0, weight=1)
        layers_frame.rowconfigure(0, weight=1)
        self.layers_notebook = ttk.Notebook(layers_frame)
        self.layers_notebook.grid(row=0, column=0, sticky="nsew")
        self.layers_notebook.bind("<<NotebookTabChanged>>", lambda event: self.refresh_chat_layers())
        main_notebook.add(layers_frame, text="Layers")

        chat_frame = self._build_chat_tab(main_notebook)
        main_notebook.add(chat_frame, text="Chat")

        log_frame = ttk.Frame(main_notebook, padding=4)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, wrap="word", height=10)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")
        main_notebook.add(log_frame, text="Log")

        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(10, 4))
        status.grid(row=3, column=0, sticky="ew")

    def _build_chat_tab(self, parent):
        frame = ttk.Frame(parent, padding=8)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        controls = ttk.Frame(frame)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(controls, text="Chat with").pack(side="left")
        self.chat_layer_combo = ttk.Combobox(
            controls,
            textvariable=self.chat_layer_var,
            values=[],
            state="readonly",
            width=32,
        )
        self.chat_layer_combo.pack(side="left", padx=(6, 12))

        ttk.Label(controls, text="Mode").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.chat_mode_var,
            values=CHAT_MODES,
            state="readonly",
            width=18,
        ).pack(side="left", padx=(6, 12))

        self.send_chat_button = ttk.Button(controls, text="Send", command=self.send_chat_message)
        self.send_chat_button.pack(side="left")
        ttk.Button(controls, text="Clear chat", command=self.clear_chat).pack(
            side="left", padx=(8, 0)
        )

        self.chat_text = tk.Text(frame, wrap="word", state="disabled", height=18)
        chat_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.chat_text.yview)
        self.chat_text.configure(yscrollcommand=chat_scroll.set)
        self.chat_text.grid(row=1, column=0, sticky="nsew")
        chat_scroll.grid(row=1, column=1, sticky="ns")

        self.chat_input = tk.Text(frame, wrap="word", height=5, undo=True)
        self.chat_input.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        return frame

    def _build_menu_bar(self):
        menu_bar = tk.Menu(self)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="New project", command=self.new_project)
        file_menu.add_separator()
        file_menu.add_command(
            label="Save session",
            accelerator="Ctrl+S",
            command=self.save_session,
        )
        file_menu.add_command(
            label="Save session as...",
            accelerator="Ctrl+Shift+S",
            command=lambda: self.save_session(save_as=True),
        )
        file_menu.add_command(label="Load session...", command=self.load_session)
        file_menu.add_separator()
        file_menu.add_checkbutton(
            label="Save keys in session",
            variable=self.save_keys_var,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menu_bar.add_cascade(label="File", menu=file_menu)
        self.configure(menu=menu_bar)

    def set_shared_key(self, provider, key, source=None):
        self.shared_keys[provider] = key.strip()
        for layer in self.layers:
            if layer is not source:
                layer.set_shared_key_value(provider, key.strip())
            layer.refresh_settings_summary()

    def add_layer(self, data=None):
        if data is None:
            data = {"name": "Layer " + str(len(self.layers) + 1)}
        layer = LayerPanel(self, data)
        self.layers.append(layer)
        self.layers_notebook.add(layer.frame, text=self.layer_tab_title(layer))
        self.layers_notebook.select(layer.frame)
        self.refresh_layer_titles()
        self.log("Created " + layer.display_name() + ".")
        return layer

    def duplicate_layer(self):
        layer = self.current_layer()
        if not layer:
            messagebox.showinfo("No layer", "Create or select a layer first.")
            return
        data = layer.to_dict(save_keys=True)
        data["id"] = make_id()
        data["name"] = layer.display_name() + " copy"
        self.add_layer(data)

    def delete_layer(self):
        index = self.current_layer_index()
        if index is None:
            messagebox.showinfo("No layer", "Create or select a layer first.")
            return
        layer = self.layers[index]
        if not messagebox.askyesno("Delete layer", "Delete " + layer.display_name() + "?"):
            return
        self.layers_notebook.forget(layer.frame)
        del self.layers[index]
        self.refresh_layer_titles()
        self.log("Deleted layer.")

    def move_layer(self, direction):
        index = self.current_layer_index()
        if index is None:
            return
        new_index = index + direction
        if new_index < 0 or new_index >= len(self.layers):
            return
        layer = self.layers.pop(index)
        self.layers.insert(new_index, layer)
        self.layers_notebook.insert(new_index, layer.frame)
        self.layers_notebook.select(layer.frame)
        self.refresh_layer_titles()

    def layer_tab_title(self, layer):
        return layer.display_name()

    def refresh_layer_titles(self):
        for layer in self.layers:
            self.layers_notebook.tab(layer.frame, text=self.layer_tab_title(layer))
            layer.refresh_settings_summary()
        self.refresh_prompt_variable_options()
        self.refresh_chat_layers()

    def refresh_chat_layers(self):
        labels = self.chat_labels()
        current = self.chat_layer_var.get()
        self.chat_layer_combo.configure(values=labels)
        if labels:
            if current not in labels:
                selected = self.current_layer_index()
                if selected is not None and selected < len(labels):
                    self.chat_layer_var.set(labels[selected])
                else:
                    self.chat_layer_var.set(labels[0])
        else:
            self.chat_layer_var.set("")

    def chat_labels(self):
        return [f"{index + 1}. {layer.display_name()}" for index, layer in enumerate(self.layers)]

    def variable_labels(self):
        labels = [label for label, token in VARIABLES]
        for index, layer in enumerate(self.layers, start=1):
            labels.append(f"Output from Layer {index}: {layer.display_name()}")
        return labels

    def variable_token(self, label):
        for base_label, token in VARIABLES:
            if label == base_label:
                return token
        prefix = "Output from Layer "
        if label.startswith(prefix):
            remainder = label[len(prefix):]
            number_text = remainder.split(":", 1)[0].strip()
            if number_text.isdigit():
                return "{layer_" + number_text + "_output}"
        return "{input}"

    def refresh_prompt_variable_options(self):
        for layer in self.layers:
            layer.refresh_variable_options()

    def current_layer_index(self):
        selected = self.layers_notebook.select()
        if not selected:
            return None
        for index, layer in enumerate(self.layers):
            if str(layer.frame) == str(selected):
                return index
        return None

    def current_layer(self):
        index = self.current_layer_index()
        if index is None:
            return None
        return self.layers[index]

    def chat_layer_index(self):
        label = self.chat_layer_var.get()
        labels = self.chat_labels()
        if label in labels:
            return labels.index(label)
        return None

    def collect_layers(self):
        return [layer.runtime_state() for layer in self.layers]

    def validate_layer_connection(self, layer_state):
        name = layer_state["name"]
        if layer_state["provider"] not in PROVIDERS:
            raise ValueError(name + ": choose a supported provider.")
        if not layer_state["api_key"]:
            raise ValueError(name + ": enter or load an API key.")
        if not layer_state["base_url"]:
            raise ValueError(name + ": enter a base URL.")
        if not layer_state["model"]:
            raise ValueError(name + ": load models and choose one.")
        if layer_state["temperature"] < 0 or layer_state["temperature"] > 2:
            raise ValueError(name + ": temperature must be between 0 and 2.")
        if layer_state["max_tokens"] <= 0:
            raise ValueError(name + ": max tokens must be greater than 0.")

    def validate_run(self, start_index):
        if not self.layers:
            raise ValueError("Create at least one layer first.")
        if start_index is None:
            raise ValueError("Select a layer first.")

        layers = self.collect_layers()
        for layer in layers[start_index:]:
            self.validate_layer_connection(layer)
            if not layer["prompt"]:
                raise ValueError(layer["name"] + ": add a prompt before running this layer.")
        return layers

    def validate_chat(self, start_index):
        if not self.layers:
            raise ValueError("Create at least one layer first.")
        if start_index is None:
            raise ValueError("Choose a layer to chat with.")

        layers = self.collect_layers()
        for index, layer in enumerate(layers[start_index:], start=start_index):
            self.validate_layer_connection(layer)
            if index > start_index and not layer["prompt"]:
                raise ValueError(layer["name"] + ": add a prompt before chat can update downstream layers.")
        return layers

    def client_for_layer(self, layer_state):
        return ProviderClient(
            layer_state["provider"],
            layer_state["api_key"],
            layer_state["base_url"],
            layer_state["temperature"],
            layer_state["max_tokens"],
        )

    def load_models_for_layer(self, layer):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Still running", "Wait for the current request to finish first.")
            return
        try:
            state = layer.runtime_state()
            self.validate_layer_connection_for_models(state)
        except Exception as exc:
            messagebox.showerror("Configuration problem", str(exc))
            return

        self.set_busy(True)
        self.log("Loading models for " + state["name"] + ".")
        self.worker = threading.Thread(
            target=self._load_models_worker,
            args=(layer.id, state),
            daemon=True,
        )
        self.worker.start()

    def validate_layer_connection_for_models(self, layer_state):
        name = layer_state["name"]
        if layer_state["provider"] not in PROVIDERS:
            raise ValueError(name + ": choose a supported provider.")
        if not layer_state["api_key"]:
            raise ValueError(name + ": enter or load an API key.")
        if not layer_state["base_url"]:
            raise ValueError(name + ": enter a base URL.")

    def _load_models_worker(self, layer_id, layer_state):
        try:
            client = self.client_for_layer(layer_state)
            models = client.list_models()
            if not models:
                raise RuntimeError("No compatible models were returned.")
            self.events.put(("models", layer_id, models))
            self.events.put(("done", "Ready"))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def run_all(self):
        self.start_run(0)

    def run_selected_and_after(self):
        self.start_run(self.current_layer_index())

    def start_run(self, start_index):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Still running", "Wait for the current request to finish first.")
            return
        try:
            layers = self.validate_run(start_index)
        except Exception as exc:
            messagebox.showerror("Configuration problem", str(exc))
            return

        global_input = self.input_text.get("1.0", "end-1c").strip()
        self.set_busy(True)
        self.log("Running layers from " + layers[start_index]["name"] + ".")
        self.worker = threading.Thread(
            target=self._run_worker,
            args=(global_input, layers, start_index),
            daemon=True,
        )
        self.worker.start()

    def _run_worker(self, global_input, layers, start_index):
        try:
            for index in range(start_index, len(layers)):
                layer = layers[index]
                self.events.put(("status", "Running " + layer["name"]))
                values = build_layer_values(
                    global_input,
                    layers,
                    index,
                    chat_history=format_chat_history(self.chat_history),
                )
                prompt = render_template(layer["prompt"], values)
                output = self.client_for_layer(layer).generate(layer["model"], prompt)
                layers[index]["output"] = output
                self.events.put(("set_layer_output", layer["id"], output))
                self.events.put(("log", "Finished " + layer["name"] + "."))
            self.events.put(("done", "Ready"))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def send_chat_message(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Still running", "Wait for the current request to finish first.")
            return
        message = self.chat_input.get("1.0", "end-1c").strip()
        if not message:
            messagebox.showinfo("Empty message", "Type a chat message ... (13 KB left)
