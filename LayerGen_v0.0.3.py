# -*- coding: utf-8 -*-
"""
LayerGen

A single-file, plain GUI for building configurable chained AI layers.

Run with:
    python LayerGen.py

This file uses only Python's standard library.
"""

import json
import os
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk


APP_TITLE = "LayerGen"
SESSION_VERSION = 7
ANTHROPIC_VERSION = "2023-06-01"
LOCAL_RUNTIME_TIMEOUT_SECONDS = 1800

PROVIDERS = ("Gemini", "OpenAI-compatible", "Anthropic", "Ollama", "Local GGUF")
DEFAULT_BASE_URLS = {
    "Gemini": "https://generativelanguage.googleapis.com/v1beta",
    "OpenAI-compatible": "https://api.openai.com/v1",
    "Anthropic": "https://api.anthropic.com/v1",
    "Ollama": "http://localhost:11434",
    "Local GGUF": "",
}
PROVIDER_ENV_KEYS = {
    "Gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "OpenAI-compatible": ("OPENAI_API_KEY", "API_KEY"),
    "Anthropic": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
    "Ollama": (),
    "Local GGUF": (),
}
KEY_SCOPES = ("Shared provider key", "Layer-specific key")
CHAT_MODES = ("Replace outputs", "Append outputs")

UI_BG = "#f4f6f8"
SURFACE = "#ffffff"
SURFACE_ALT = "#f8fafc"
SURFACE_SOFT = "#eef2f7"
BORDER = "#d7dde5"
TEXT = "#111827"
MUTED = "#64748b"
ACCENT = "#2563eb"
CODE_BG = "#fbfcfd"
CODE_GUTTER = "#eef2f7"
CODE_BORDER = "#d8dee8"
SELECTION_BG = "#bfdbfe"

UI_FONT = ("Segoe UI", 10)
UI_FONT_BOLD = ("Segoe UI Semibold", 10)
TITLE_FONT = ("Segoe UI Semibold", 15)
SMALL_FONT = ("Segoe UI", 9)
MONO_FONT = ("Consolas", 10)

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


def normalize_huggingface_repo_id(value):
    return value.strip().strip('"').strip("'").strip().strip("/")


def is_huggingface_repo_id(value):
    repo_id = normalize_huggingface_repo_id(value)
    if not repo_id:
        return False
    if "\\" in repo_id or repo_id.lower().startswith(("http://", "https://")):
        return False
    repo_part = repo_id.split(":", 1)[0]
    if repo_part.count("/") != 1:
        return False
    namespace, model = repo_part.split("/", 1)
    name_pattern = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    quant_pattern = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    if not re.match(name_pattern, namespace) or not re.match(name_pattern, model):
        return False
    if ":" in repo_id:
        quant = repo_id.split(":", 1)[1]
        if not re.match(quant_pattern, quant):
            return False
    return True


def looks_like_python_executable(executable):
    name = Path(executable).name.lower()
    return name in ("python.exe", "python3.exe", "pythonw.exe")


def llama_runtime_has_adjacent_files(executable):
    runtime_path = Path(executable)
    if not runtime_path.exists() or runtime_path.name.lower() != "llama-cli.exe":
        return True
    runtime_dir = runtime_path.parent
    sibling_patterns = ("llama.dll", "ggml*.dll", "gguf*.dll")
    for pattern in sibling_patterns:
        if any(runtime_dir.glob(pattern)):
            return True
    return False


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


def extract_text_from_ollama_response(data):
    if isinstance(data.get("response"), str):
        return data["response"].strip()

    message = data.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"].strip()

    raise RuntimeError("Ollama did not return text content.")


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


def provider_requires_api_key(provider):
    return provider in ("Gemini", "Anthropic")


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


def extract_model_names_from_text(text):
    cleaned = text.strip()
    if not cleaned:
        return []

    def collect_from_item(item, names):
        if isinstance(item, str):
            value = item.strip()
            if value:
                names.append(value)
        elif isinstance(item, dict):
            for key in ("id", "name", "model"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    names.append(value.strip())
                    return

    names = []
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            for item in data:
                collect_from_item(item, names)
        elif isinstance(data, dict):
            for key in ("models", "data", "model_options"):
                value = data.get(key)
                if isinstance(value, list):
                    for item in value:
                        collect_from_item(item, names)
            collect_from_item(data, names)
    except json.JSONDecodeError:
        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "," in line:
                for part in line.split(","):
                    value = part.strip()
                    if value:
                        names.append(value)
            else:
                names.append(line)

    return sorted(set(names), key=model_sort_key)


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


def prompt_dependencies(prompt, layer_index, layer_count):
    dependencies = []
    seen = set()

    def add_dependency(source_index, label):
        key = (source_index, layer_index)
        if source_index == layer_index or key in seen:
            return
        seen.add(key)
        dependencies.append(
            {
                "source": source_index,
                "target": layer_index,
                "label": label,
            }
        )

    if "{input}" in prompt:
        add_dependency(-1, "input")
    if "{previous_output}" in prompt and layer_index > 0:
        add_dependency(layer_index - 1, "previous")

    for match in re.finditer(r"\{layer_(\d+)_output\}", prompt):
        source_index = int(match.group(1)) - 1
        if 0 <= source_index < layer_count:
            add_dependency(source_index, "layer output")

    if "{all_previous_outputs}" in prompt:
        for source_index in range(layer_index):
            add_dependency(source_index, "all previous")

    return dependencies


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
    def __init__(
        self,
        provider,
        api_key,
        base_url,
        temperature,
        max_tokens,
        status_callback=None,
        notice_callback=None,
    ):
        self.provider = provider
        self.api_key = api_key.strip()
        self.base_url = normalize_base_url(base_url)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.status_callback = status_callback
        self.notice_callback = notice_callback

        if self.provider not in PROVIDERS:
            raise ValueError("Choose a supported provider.")
        if provider_requires_api_key(self.provider) and not self.api_key:
            raise ValueError("Enter or load an API key.")
        if self.provider == "Local GGUF":
            if not self.base_url:
                raise ValueError("Choose a local runtime executable for Local GGUF.")
        elif not self.base_url:
            raise ValueError("Enter a base URL.")

    def _report_status(self, message):
        if self.status_callback:
            self.status_callback(message)

    def _report_notice(self, title, message):
        if self.notice_callback:
            self.notice_callback(title, message)

    def list_models(self):
        if self.provider == "Gemini":
            return self._list_gemini_models()
        if self.provider == "Anthropic":
            return self._list_anthropic_models()
        if self.provider == "Ollama":
            return self._list_ollama_models()
        if self.provider == "Local GGUF":
            raise RuntimeError("Use Models > Import local model file for Local GGUF.")
        return self._list_openai_compatible_models()

    def generate(self, model_name, prompt):
        model_name = model_name.strip()
        if not model_name:
            raise ValueError("Choose a model.")

        if self.provider == "Gemini":
            return self._generate_gemini(model_name, prompt)
        if self.provider == "Anthropic":
            return self._generate_anthropic(model_name, prompt)
        if self.provider == "Ollama":
            return self._generate_ollama(model_name, prompt)
        if self.provider == "Local GGUF":
            return self._generate_local_gguf(model_name, prompt)
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
        headers = {}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        data = request_json(join_url(self.base_url, "models"), headers=headers)
        model_names = []
        for model in data.get("data", []):
            if isinstance(model, dict) and model.get("id"):
                model_names.append(model["id"])
        return sorted(set(model_names), key=model_sort_key)

    def _generate_openai_compatible(self, model_name, prompt):
        headers = {}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
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

    def _list_ollama_models(self):
        data = request_json(join_url(self.base_url, "api/tags"))
        model_names = []
        for model in data.get("models", []):
            if isinstance(model, dict) and model.get("name"):
                model_names.append(model["name"])
        return sorted(set(model_names), key=model_sort_key)

    def _generate_ollama(self, model_name, prompt):
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        return extract_text_from_ollama_response(
            request_json(
                join_url(self.base_url, "api/generate"),
                method="POST",
                payload=payload,
            )
        )

    def _generate_local_gguf(self, model_name, prompt):
        executable = self.base_url.strip().strip('"')
        model_path = model_name.strip().strip('"')
        if not executable:
            raise RuntimeError("Choose a llama.cpp-style runtime executable.")
        if looks_like_python_executable(executable):
            raise RuntimeError(
                "The selected runtime is Python, not llama-cli.exe. Choose the official "
                "llama.cpp llama-cli.exe file instead."
            )
        if not model_path:
            raise RuntimeError("Choose a local GGUF model file or Hugging Face repo ID.")

        if is_huggingface_repo_id(model_path):
            command = [executable, "-hf", model_path]
        else:
            command = [executable, "-m", model_path]
        command.extend(
            [
                "-p",
                prompt,
                "-n",
                str(self.max_tokens),
                "--temp",
                str(self.temperature),
                "--no-display-prompt",
                "--simple-io",
            ]
        )
        runtime_path = Path(executable)
        run_cwd = str(runtime_path.parent) if runtime_path.exists() else None
        self._report_status(
            "Starting local model. First Hugging Face runs may spend several minutes downloading."
        )
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=run_cwd,
            )
        except FileNotFoundError:
            raise RuntimeError("The local runtime executable was not found.")

        start_time = time.monotonic()
        next_status_seconds = 60
        notice_shown = False
        while True:
            try:
                output_text, error_text = process.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                elapsed = int(time.monotonic() - start_time)
                if elapsed >= next_status_seconds:
                    minutes = max(1, elapsed // 60)
                    self._report_status(
                        f"Local model still running ({minutes} min). First Hugging Face runs may still be downloading."
                    )
                    next_status_seconds += 60
                if elapsed >= 600 and not notice_shown:
                    self._report_notice(
                        "Local model still running",
                        "The local runtime has been busy for about 10 minutes. This can be normal on the first Hugging Face run if it is downloading the model. If it never finishes, try a smaller model, lower max tokens, or run the same llama-cli command in Command Prompt to see download/runtime messages.",
                    )
                    notice_shown = True
                if elapsed >= LOCAL_RUNTIME_TIMEOUT_SECONDS:
                    process.kill()
                    output_text, error_text = process.communicate()
                    minutes = max(1, elapsed // 60)
                    raise RuntimeError(
                        f"The local model run timed out after about {minutes} minutes. First-time downloads can be slow; otherwise try a smaller model or lower max tokens."
                    )

        output = (output_text or "").strip()
        error = (error_text or "").strip()
        if process.returncode != 0:
            if error or output:
                detail = error or output
            elif not llama_runtime_has_adjacent_files(executable):
                detail = (
                    "No output returned. This usually happens when llama-cli.exe was copied "
                    "without the DLL files from the llama.cpp zip. Select the llama-cli.exe "
                    "inside the extracted llama.cpp folder, or copy the whole extracted folder "
                    "to Downloads instead of copying only llama-cli.exe."
                )
            else:
                detail = (
                    "No output returned. Try this in Command Prompt to see the runtime's own "
                    f"message: \"{executable}\" -hf {model_path} -p \"hello\" -n 20 --simple-io"
                )
            raise RuntimeError("Local model run failed: " + detail[:1200])
        if output:
            return output
        if error:
            return error
        raise RuntimeError(
            "The local model did not return output. Try a smaller model or run "
            f"\"{executable}\" -hf {model_path} -p \"hello\" -n 20 --simple-io in Command Prompt."
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


def draw_rounded_rect(canvas, x1, y1, x2, y2, radius=12, **kwargs):
    radius = max(2, min(radius, int((x2 - x1) / 2), int((y2 - y1) / 2)))
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=20, **kwargs)


class CodeCell(tk.Frame):
    def __init__(
        self,
        parent,
        title,
        height=10,
        wrap="none",
        line_numbers=True,
        text_font=MONO_FONT,
    ):
        super().__init__(parent, bg=BORDER, highlightthickness=0, padx=1, pady=1)
        self.line_numbers = line_numbers
        self._updating_numbers = False

        self.card = tk.Frame(self, bg=SURFACE, highlightthickness=0)
        self.card.pack(fill="both", expand=True)

        self.header = tk.Frame(self.card, bg=SURFACE_ALT, height=34)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        self.header_left = tk.Frame(self.header, bg=SURFACE_ALT)
        self.header_left.pack(side="left", fill="x", expand=True, padx=10)
        tk.Label(
            self.header_left,
            text=title,
            bg=SURFACE_ALT,
            fg=TEXT,
            font=UI_FONT_BOLD,
        ).pack(side="left")

        self.header_actions = tk.Frame(self.header, bg=SURFACE_ALT)
        self.header_actions.pack(side="right", padx=8)

        self.body = tk.Frame(self.card, bg=CODE_BG)
        self.body.pack(fill="both", expand=True)
        self.body.columnconfigure(1 if line_numbers else 0, weight=1)
        self.body.rowconfigure(0, weight=1)

        if line_numbers:
            self.gutter = tk.Text(
                self.body,
                width=4,
                height=height,
                wrap="none",
                bd=0,
                padx=6,
                pady=8,
                bg=CODE_GUTTER,
                fg=MUTED,
                font=text_font,
                state="disabled",
                highlightthickness=0,
                takefocus=0,
            )
            self.gutter.grid(row=0, column=0, sticky="ns")
            text_column = 1
        else:
            self.gutter = None
            text_column = 0

        self.text = tk.Text(
            self.body,
            wrap=wrap,
            undo=True,
            height=height,
            bd=0,
            padx=10,
            pady=8,
            bg=CODE_BG,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=SELECTION_BG,
            selectforeground=TEXT,
            font=text_font,
            highlightthickness=0,
        )
        self.text.grid(row=0, column=text_column, sticky="nsew")

        self.y_scroll = ttk.Scrollbar(self.body, orient="vertical", command=self._yview)
        self.y_scroll.grid(row=0, column=text_column + 1, sticky="ns")
        self.text.configure(yscrollcommand=self._text_yscroll)

        if wrap == "none":
            self.x_scroll = ttk.Scrollbar(self.body, orient="horizontal", command=self.text.xview)
            self.x_scroll.grid(row=1, column=text_column, sticky="ew")
            self.text.configure(xscrollcommand=self.x_scroll.set)
        else:
            self.x_scroll = None

        self.text.bind("<<Modified>>", self._text_modified)
        self.text.bind("<Configure>", lambda event: self.update_line_numbers())
        self.text.edit_modified(False)
        self.update_line_numbers()

    def add_action(self, label, command):
        button = ttk.Button(
            self.header_actions,
            text=label,
            command=command,
            style="Tool.TButton",
        )
        button.pack(side="left", padx=(6, 0))
        return button

    def _yview(self, *args):
        self.text.yview(*args)
        if self.gutter is not None:
            self.gutter.yview(*args)

    def _text_yscroll(self, first, last):
        self.y_scroll.set(first, last)
        if self.gutter is not None:
            self.gutter.yview_moveto(first)

    def _text_modified(self, event=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.update_line_numbers()

    def update_line_numbers(self):
        if not self.line_numbers or self.gutter is None or self._updating_numbers:
            return
        self._updating_numbers = True
        try:
            last_line = int(self.text.index("end-1c").split(".", 1)[0])
            numbers = "\n".join(str(number) for number in range(1, last_line + 1))
            self.gutter.configure(state="normal")
            self.gutter.delete("1.0", "end")
            self.gutter.insert("1.0", numbers)
            self.gutter.configure(state="disabled")
            self.gutter.yview_moveto(self.text.yview()[0])
        finally:
            self._updating_numbers = False


class LayerPanel:
    def __init__(self, app, data=None):
        self.app = app
        self.id = (data or {}).get("id") or make_id()
        self.frame = ttk.Frame(app.layers_notebook, padding=12, style="App.TFrame")
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
        self.prompt_cell.update_line_numbers()
        self.output_cell.update_line_numbers()
        self.model_combo.configure(values=self.model_options)
        self._sync_key_from_scope()
        self.refresh_settings_summary()

    def _build_ui(self):
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=2)
        self.frame.rowconfigure(2, weight=3)

        config = ttk.Frame(self.frame, padding=12, style="Card.TFrame")
        config.grid(row=0, column=0, sticky="ew")
        config.columnconfigure(2, weight=1)
        config.columnconfigure(4, weight=1)
        config.columnconfigure(6, weight=2)

        self.settings_button = ttk.Menubutton(config, text="Settings")
        self.settings_menu = tk.Menu(self.settings_button, tearoff=0)
        self.settings_button.configure(menu=self.settings_menu)
        self._build_settings_menu()
        self.settings_button.grid(row=0, column=0, sticky="w", padx=(0, 14))

        ttk.Label(config, text="Provider", style="Muted.TLabel").grid(row=0, column=1, sticky="w")
        provider_combo = ttk.Combobox(
            config,
            textvariable=self.provider_var,
            values=PROVIDERS,
            state="readonly",
            width=18,
        )
        provider_combo.grid(row=0, column=2, sticky="ew", padx=(6, 14))
        provider_combo.bind("<<ComboboxSelected>>", self._provider_changed)

        ttk.Label(config, text="Language", style="Muted.TLabel").grid(row=0, column=3, sticky="w")
        ttk.Combobox(
            config,
            textvariable=self.language_var,
            values=list(LANGUAGE_EXTENSIONS.keys()),
            width=14,
        ).grid(row=0, column=4, sticky="ew", padx=(6, 14))

        ttk.Label(config, text="Model", style="Muted.TLabel").grid(row=0, column=5, sticky="w")
        self.model_combo = ttk.Combobox(
            config,
            textvariable=self.model_var,
            values=self.model_options,
            state="readonly",
        )
        self.model_combo.bind("<<ComboboxSelected>>", lambda event: self.app.schedule_flowchart_refresh())
        self.model_combo.grid(row=0, column=6, sticky="ew", padx=(6, 14))
        self.models_button = ttk.Menubutton(config, text="Models")
        self.models_menu = tk.Menu(self.models_button, tearoff=0)
        self.models_button.configure(menu=self.models_menu)
        self._build_models_menu()
        self.models_button.grid(row=0, column=7, sticky="ew")

        self.settings_summary_var = tk.StringVar()
        ttk.Label(
            config,
            textvariable=self.settings_summary_var,
            anchor="w",
            style="Muted.TLabel",
        ).grid(
            row=1, column=0, columnspan=8, sticky="ew", pady=(8, 0)
        )
        self.refresh_settings_summary()

        self.prompt_cell = CodeCell(
            self.frame,
            "Prompt",
            height=10,
            wrap="word",
            line_numbers=True,
        )
        self.prompt_cell.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        ttk.Label(
            self.prompt_cell.header_left,
            text="Insert",
            style="CellMuted.TLabel",
        ).pack(side="left", padx=(14, 4))
        self.variable_combo = ttk.Combobox(
            self.prompt_cell.header_left,
            textvariable=self.variable_var,
            values=self.app.variable_labels(),
            state="readonly",
            width=24,
        )
        self.variable_combo.pack(side="left", padx=(0, 6))
        ttk.Button(
            self.prompt_cell.header_left,
            text="Insert",
            command=self.insert_variable,
            style="Tool.TButton",
        ).pack(
            side="left"
        )
        self.prompt_cell.add_action("Clear", self.clear_prompt)
        self.prompt_text = self.prompt_cell.text
        self.prompt_text.bind(
            "<KeyRelease>",
            lambda event: self.app.schedule_flowchart_refresh(),
        )

        self.output_cell = CodeCell(
            self.frame,
            "Output",
            height=15,
            wrap="none",
            line_numbers=True,
        )
        self.output_cell.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        self.output_cell.add_action("Copy", self.copy_output)
        self.output_cell.add_action("Save", self.save_output)
        self.output_cell.add_action("Clear", self.clear_output)
        self.output_text = self.output_cell.text

    def _build_models_menu(self):
        self.models_menu.delete(0, "end")
        self.models_menu.add_command(
            label="Load from provider",
            command=lambda: self.app.load_models_for_layer(self),
        )
        self.models_menu.add_command(
            label="Import local model file...",
            command=self.import_local_model_file,
        )
        self.models_menu.add_command(
            label="Import local model folder...",
            command=self.import_local_model_folder,
        )
        self.models_menu.add_command(
            label="Import Hugging Face repo...",
            command=self.import_huggingface_model,
        )
        self.models_menu.add_command(
            label="Import model list from file...",
            command=self.import_models,
        )
        self.models_menu.add_command(
            label="Enter model name...",
            command=self.enter_model_name,
        )
        self.models_menu.add_separator()
        self.models_menu.add_command(label="Clear model list", command=self.clear_models)

    def _build_settings_menu(self):
        self.settings_menu.delete(0, "end")
        self.settings_menu.add_command(label="Layer name...", command=self.edit_layer_name)
        self.settings_menu.add_command(label="Endpoint / runtime...", command=self.edit_base_url)
        self.settings_menu.add_command(label="Choose local runtime...", command=self.choose_local_runtime)
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
        provider = self.provider_var.get()
        if provider_requires_api_key(provider):
            key_status = "key set" if self.effective_api_key() else "no key"
        elif provider == "Local GGUF":
            key_status = "runtime set" if self.base_url_var.get().strip() else "runtime missing"
        else:
            key_status = "key set" if self.effective_api_key() else "no key needed"
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
        if self.provider_var.get() == "Local GGUF":
            title = "Local runtime"
            prompt = "Path to llama.cpp executable:"
        else:
            title = "Endpoint"
            prompt = "Base URL:"
        base_url = simpledialog.askstring(
            title,
            prompt,
            initialvalue=self.base_url_var.get(),
            parent=self.app,
        )
        if base_url is None:
            return
        self.base_url_var.set(base_url.strip())
        self.refresh_settings_summary()

    def choose_local_runtime(self):
        path = filedialog.askopenfilename(
            title="Choose local runtime",
            filetypes=[
                ("Runtime executables", "*.exe *.bat *.cmd"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        if self.provider_var.get() != "Local GGUF":
            self.provider_var.set("Local GGUF")
            self.set_model_options([])
        self.base_url_var.set(path)
        self.refresh_settings_summary()
        self.app.schedule_flowchart_refresh()
        self.app.log("Selected local runtime for " + self.display_name() + ".")

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

    def set_model_options(self, models, selected=None):
        self.model_options = sorted(set(models), key=model_sort_key)
        self.model_combo.configure(values=self.model_options)
        if not self.model_options:
            self.model_var.set("")
        elif selected and selected in self.model_options:
            self.model_var.set(selected)
        elif self.model_var.get() not in self.model_options:
            self.model_var.set(self.model_options[0])
        self.app.schedule_flowchart_refresh()

    def import_models(self):
        path = filedialog.askopenfilename(
            title="Import model list",
            filetypes=[
                ("Model list files", "*.txt *.csv *.json"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
            models = extract_model_names_from_text(text)
            if not models:
                raise ValueError("No model names were found in that file.")
            current = self.model_var.get().strip()
            self.set_model_options(models, selected=current)
            self.app.status_var.set("Imported models")
            self.app.log(
                f"Imported {len(models)} models for {self.display_name()} from: {path}"
            )
        except Exception as exc:
            messagebox.showerror("Could not import models", str(exc))

    def import_local_model_file(self):
        path = filedialog.askopenfilename(
            title="Import local model file",
            filetypes=[
                ("GGUF model files", "*.gguf"),
                ("Model files", "*.gguf *.bin"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        if self.provider_var.get() != "Local GGUF":
            self.provider_var.set("Local GGUF")
            self.base_url_var.set(DEFAULT_BASE_URLS.get("Local GGUF", ""))
            self._sync_key_from_scope()
        models = list(self.model_options)
        models.append(path)
        self.set_model_options(models, selected=path)
        self.refresh_settings_summary()
        self.app.status_var.set("Imported local model")
        self.app.log("Imported local model for " + self.display_name() + ": " + path)

    def import_local_model_folder(self):
        folder = filedialog.askdirectory(title="Import local model folder")
        if not folder:
            return
        try:
            root = Path(folder)
            paths = []
            for pattern in ("*.gguf", "*.bin"):
                paths.extend(str(path) for path in root.rglob(pattern) if path.is_file())
            if not paths:
                raise ValueError("No .gguf or .bin model files were found in that folder.")
            if self.provider_var.get() != "Local GGUF":
                self.provider_var.set("Local GGUF")
                self.base_url_var.set(DEFAULT_BASE_URLS.get("Local GGUF", ""))
                self._sync_key_from_scope()
            models = list(self.model_options)
            models.extend(paths)
            self.set_model_options(models, selected=paths[0])
            self.refresh_settings_summary()
            self.app.status_var.set("Imported local models")
            self.app.log(
                f"Imported {len(paths)} local models for {self.display_name()} from: {folder}"
            )
        except Exception as exc:
            messagebox.showerror("Could not import local models", str(exc))

    def import_huggingface_model(self):
        initial = self.model_var.get()
        if not is_huggingface_repo_id(initial):
            initial = ""
        repo_id = simpledialog.askstring(
            "Hugging Face model",
            "Repo ID, such as author/model or author/model:Q4_K_M:",
            initialvalue=initial,
            parent=self.app,
        )
        if repo_id is None:
            return
        repo_id = normalize_huggingface_repo_id(repo_id)
        if not is_huggingface_repo_id(repo_id):
            messagebox.showerror(
                "Invalid repo ID",
                "Use the Hugging Face format author/model, optionally author/model:quant.",
            )
            return
        if self.provider_var.get() != "Local GGUF":
            self.provider_var.set("Local GGUF")
            self.base_url_var.set(DEFAULT_BASE_URLS.get("Local GGUF", ""))
            self._sync_key_from_scope()
        models = list(self.model_options)
        models.append(repo_id)
        self.set_model_options(models, selected=repo_id)
        self.refresh_settings_summary()
        self.app.status_var.set("Imported Hugging Face repo")
        self.app.log("Imported Hugging Face repo for " + self.display_name() + ": " + repo_id)
        if not self.base_url_var.get().strip():
            messagebox.showinfo(
                "Choose local runtime",
                "This repo is ready in the model dropdown. Before running it, choose a llama.cpp runtime in Settings.",
            )

    def enter_model_name(self):
        model_name = simpledialog.askstring(
            "Model name",
            "Model name:",
            initialvalue=self.model_var.get(),
            parent=self.app,
        )
        if model_name is None:
            return
        model_name = model_name.strip()
        if not model_name:
            return
        models = list(self.model_options)
        models.append(model_name)
        self.set_model_options(models, selected=model_name)
        self.app.status_var.set("Model added")
        self.app.log(f"Added model {model_name} to {self.display_name()}.")

    def clear_models(self):
        self.set_model_options([])
        self.app.status_var.set("Model list cleared")
        self.app.log("Cleared model list for " + self.display_name() + ".")

    def _provider_changed(self, event=None):
        provider = self.provider_var.get()
        self.base_url_var.set(DEFAULT_BASE_URLS.get(provider, ""))
        self.set_model_options([])
        self._sync_key_from_scope()
        self.refresh_settings_summary()
        self.app.schedule_flowchart_refresh()
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
        self.app.schedule_flowchart_refresh()

    def refresh_variable_options(self):
        labels = self.app.variable_labels()
        self.variable_combo.configure(values=labels)
        if self.variable_var.get() not in labels:
            self.variable_var.set(labels[0])

    def clear_prompt(self):
        self.prompt_text.delete("1.0", "end")
        if hasattr(self, "prompt_cell"):
            self.prompt_cell.update_line_numbers()
        self.app.schedule_flowchart_refresh()

    def clear_output(self):
        self.output_text.delete("1.0", "end")
        if hasattr(self, "output_cell"):
            self.output_cell.update_line_numbers()

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
        if hasattr(self, "output_cell"):
            self.output_cell.update_line_numbers()

    def append_output(self, value):
        existing = self.get_output()
        if existing:
            self.output_text.insert("end", "\n\n" + value.strip())
        else:
            self.output_text.insert("end", value.strip())
        self.output_text.see("end")
        if hasattr(self, "output_cell"):
            self.output_cell.update_line_numbers()

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
        self.configure(bg=UI_BG)
        self._configure_style()

        self.events = queue.Queue()
        self.worker = None
        self.layers = []
        self.chat_history = []
        self.session_path = None
        self.flow_refresh_after_id = None
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

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=UI_FONT)
        style.configure("App.TFrame", background=UI_BG)
        style.configure("Toolbar.TFrame", background=UI_BG)
        style.configure("Card.TFrame", background=SURFACE, relief="flat")
        style.configure("Cell.TFrame", background=SURFACE)
        style.configure("TLabel", background=UI_BG, foreground=TEXT, font=UI_FONT)
        style.configure("Title.TLabel", background=UI_BG, foreground=TEXT, font=TITLE_FONT)
        style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED, font=SMALL_FONT)
        style.configure("CellMuted.TLabel", background=SURFACE_ALT, foreground=MUTED, font=SMALL_FONT)
        style.configure("Status.TLabel", background=UI_BG, foreground=MUTED, font=SMALL_FONT)
        style.configure("TButton", padding=(10, 5), font=UI_FONT)
        style.configure("Tool.TButton", padding=(8, 3), font=SMALL_FONT)
        style.configure("TMenubutton", padding=(10, 5), font=UI_FONT)
        style.configure("TCheckbutton", background=UI_BG, foreground=TEXT, font=UI_FONT)
        style.configure("TNotebook", background=UI_BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            padding=(14, 7),
            background=SURFACE_SOFT,
            foreground=TEXT,
            font=UI_FONT,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", SURFACE), ("active", "#e5eaf1")],
            foreground=[("selected", TEXT), ("active", TEXT)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=SURFACE,
            background=SURFACE,
            foreground=TEXT,
            arrowsize=14,
        )
        style.configure(
            "Vertical.TScrollbar",
            background=SURFACE_SOFT,
            troughcolor=UI_BG,
            bordercolor=UI_BG,
            arrowcolor=MUTED,
        )
        style.configure(
            "Horizontal.TScrollbar",
            background=SURFACE_SOFT,
            troughcolor=UI_BG,
            bordercolor=UI_BG,
            arrowcolor=MUTED,
        )

    def _build_ui(self):
        self._build_menu_bar()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(self, padding=(14, 12, 14, 8), style="Toolbar.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew")

        ttk.Label(toolbar, text="LayerGen", style="Title.TLabel").pack(side="left", padx=(0, 18))
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

        self.input_cell = CodeCell(
            self,
            "Project input",
            height=4,
            wrap="word",
            line_numbers=False,
            text_font=UI_FONT,
        )
        self.input_cell.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.input_text = self.input_cell.text

        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.grid(row=2, column=0, sticky="nsew", padx=14)
        self.main_notebook.bind("<<NotebookTabChanged>>", self._main_tab_changed)

        layers_frame = ttk.Frame(self.main_notebook, padding=6, style="App.TFrame")
        layers_frame.columnconfigure(0, weight=1)
        layers_frame.rowconfigure(0, weight=1)
        self.layers_notebook = ttk.Notebook(layers_frame)
        self.layers_notebook.grid(row=0, column=0, sticky="nsew")
        self.layers_notebook.bind("<<NotebookTabChanged>>", lambda event: self.refresh_chat_layers())
        self.main_notebook.add(layers_frame, text="Layers")

        chat_frame = self._build_chat_tab(self.main_notebook)
        self.main_notebook.add(chat_frame, text="Chat")

        flow_frame = self._build_flow_tab(self.main_notebook)
        self.main_notebook.add(flow_frame, text="Flowchart")

        log_frame = ttk.Frame(self.main_notebook, padding=8, style="App.TFrame")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_cell = CodeCell(
            log_frame,
            "Log",
            height=10,
            wrap="word",
            line_numbers=False,
            text_font=UI_FONT,
        )
        self.log_cell.grid(row=0, column=0, sticky="nsew")
        self.log_text = self.log_cell.text
        self.main_notebook.add(log_frame, text="Log")

        status = ttk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            padding=(14, 5),
            style="Status.TLabel",
        )
        status.grid(row=3, column=0, sticky="ew")

    def _build_chat_tab(self, parent):
        frame = ttk.Frame(parent, padding=12, style="App.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        controls = ttk.Frame(frame, padding=12, style="Card.TFrame")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(controls, text="Chat with", style="Muted.TLabel").pack(side="left")
        self.chat_layer_combo = ttk.Combobox(
            controls,
            textvariable=self.chat_layer_var,
            values=[],
            state="readonly",
            width=32,
        )
        self.chat_layer_combo.pack(side="left", padx=(6, 14))

        ttk.Label(controls, text="Mode", style="Muted.TLabel").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.chat_mode_var,
            values=CHAT_MODES,
            state="readonly",
            width=18,
        ).pack(side="left", padx=(6, 12))

        ttk.Button(controls, text="Clear chat", command=self.clear_chat).pack(side="right")

        self.chat_cell = CodeCell(
            frame,
            "Transcript",
            height=18,
            wrap="word",
            line_numbers=False,
            text_font=UI_FONT,
        )
        self.chat_cell.grid(row=1, column=0, sticky="nsew")
        self.chat_text = self.chat_cell.text
        self.chat_text.configure(state="disabled")

        self.chat_input_cell = CodeCell(
            frame,
            "Message",
            height=5,
            wrap="word",
            line_numbers=False,
            text_font=UI_FONT,
        )
        self.chat_input_cell.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.send_chat_button = self.chat_input_cell.add_action("Send", self.send_chat_message)
        self.chat_input = self.chat_input_cell.text
        return frame

    def _build_flow_tab(self, parent):
        frame = ttk.Frame(parent, padding=12, style="App.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        controls = ttk.Frame(frame, padding=12, style="Card.TFrame")
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Button(controls, text="Refresh", command=self.refresh_flowchart).pack(side="left")

        self.flow_canvas = tk.Canvas(
            frame,
            background=SURFACE,
            highlightthickness=1,
            highlightbackground=CODE_BORDER,
        )
        flow_y = ttk.Scrollbar(frame, orient="vertical", command=self.flow_canvas.yview)
        flow_x = ttk.Scrollbar(frame, orient="horizontal", command=self.flow_canvas.xview)
        self.flow_canvas.configure(yscrollcommand=flow_y.set, xscrollcommand=flow_x.set)
        self.flow_canvas.grid(row=1, column=0, sticky="nsew")
        flow_y.grid(row=1, column=1, sticky="ns")
        flow_x.grid(row=2, column=0, sticky="ew")
        self.flow_canvas.bind("<Configure>", lambda event: self.schedule_flowchart_refresh())
        return frame

    def _main_tab_changed(self, event=None):
        selected = self.main_notebook.select()
        if selected and self.main_notebook.tab(selected, "text") == "Flowchart":
            self.refresh_flowchart()

    def schedule_flowchart_refresh(self):
        if not hasattr(self, "flow_canvas"):
            return
        if self.flow_refresh_after_id is not None:
            try:
                self.after_cancel(self.flow_refresh_after_id)
            except tk.TclError:
                pass
        self.flow_refresh_after_id = self.after(250, self.refresh_flowchart)

    def refresh_flowchart(self):
        if not hasattr(self, "flow_canvas"):
            return
        self.flow_refresh_after_id = None
        canvas = self.flow_canvas
        canvas.delete("all")

        layers = [
            {
                "name": layer.display_name(),
                "provider": layer.provider_var.get(),
                "model": layer.model_var.get().strip(),
                "prompt": layer.get_prompt(),
            }
            for layer in self.layers
        ]

        canvas_width = max(canvas.winfo_width(), 920)
        canvas_height = max(canvas.winfo_height(), 360)
        if not layers:
            canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text="No layers yet",
                fill="#5f6b7a",
                font=("Segoe UI", 12),
            )
            canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))
            return

        node_w = 230
        node_h = 92
        gap_x = 96
        top = 92
        input_x = 36
        layer_x = 238
        full_width = layer_x + len(layers) * (node_w + gap_x) + 48
        full_height = 340

        input_box = (input_x, top + 14, input_x + 138, top + 76)
        node_boxes = []
        for index in range(len(layers)):
            x = layer_x + index * (node_w + gap_x)
            node_boxes.append((x, top, x + node_w, top + node_h))

        edges = []
        for index, layer in enumerate(layers):
            edges.extend(prompt_dependencies(layer["prompt"], index, len(layers)))

        color_map = {
            "input": "#6b7280",
            "previous": "#0f766e",
            "all previous": "#8a6d3b",
            "layer output": "#305f9f",
        }
        for edge_index, edge in enumerate(edges):
            source = edge["source"]
            target = edge["target"]
            label = edge["label"]
            if target < 0 or target >= len(node_boxes):
                continue

            if source == -1:
                sx = input_box[2]
                sy = (input_box[1] + input_box[3]) / 2
            elif 0 <= source < len(node_boxes):
                sx = node_boxes[source][2]
                sy = (node_boxes[source][1] + node_boxes[source][3]) / 2
            else:
                continue

            tx = node_boxes[target][0]
            ty = (node_boxes[target][1] + node_boxes[target][3]) / 2
            color = color_map.get(label, "#305f9f")

            if source < target:
                offset = ((edge_index % 5) - 2) * 10
                mid_x = (sx + tx) / 2
                points = [sx, sy, mid_x, sy + offset, mid_x, ty + offset, tx, ty]
                text_x = mid_x
                text_y = min(sy, ty) + offset - 14
            else:
                route_y = top + node_h + 44 + (edge_index % 5) * 18
                points = [sx, sy, sx + 36, route_y, tx - 36, route_y, tx, ty]
                text_x = (sx + tx) / 2
                text_y = route_y - 12

            canvas.create_line(
                points,
                arrow=tk.LAST,
                fill=color,
                width=2,
                smooth=True,
            )
            canvas.create_text(
                text_x,
                text_y,
                text=label,
                fill=color,
                font=("Segoe UI", 8),
            )

        self._draw_flow_node(
            canvas,
            input_box,
            "Project input",
            "",
            "#f3f4f6",
            "#6b7280",
        )

        for index, layer in enumerate(layers):
            title = f"{index + 1}. {layer['name']}"
            model = layer["model"] or "(model not selected)"
            subtitle = layer["provider"] + "\n" + model
            self._draw_flow_node(
                canvas,
                node_boxes[index],
                title,
                subtitle,
                "#f8fafc",
                "#475569",
            )

        if not edges:
            canvas.create_text(
                36,
                top + node_h + 70,
                text="No prompt dependencies detected",
                anchor="w",
                fill="#6b7280",
                font=("Segoe UI", 10),
            )

        canvas.configure(
            scrollregion=(
                0,
                0,
                max(canvas_width, full_width),
                max(canvas_height, full_height),
            )
        )

    def _draw_flow_node(self, canvas, box, title, subtitle, fill, outline):
        x1, y1, x2, y2 = box
        draw_rounded_rect(
            canvas,
            x1,
            y1,
            x2,
            y2,
            radius=14,
            fill=fill,
            outline=outline,
            width=1.5,
        )
        canvas.create_text(
            x1 + 12,
            y1 + 16,
            text=self._short_canvas_text(title, 28),
            anchor="w",
            fill="#111827",
            font=("Segoe UI", 10, "bold"),
        )
        if subtitle:
            canvas.create_text(
                x1 + 12,
                y1 + 44,
                text=self._short_canvas_text(subtitle, 44),
                anchor="nw",
                fill="#334155",
                font=("Segoe UI", 9),
                width=max(80, int(x2 - x1 - 24)),
            )

    def _short_canvas_text(self, text, limit):
        text = str(text).strip()
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)] + "..."

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
        self.schedule_flowchart_refresh()

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
        provider = layer_state["provider"]
        if provider not in PROVIDERS:
            raise ValueError(name + ": choose a supported provider.")
        if provider_requires_api_key(provider) and not layer_state["api_key"]:
            raise ValueError(name + ": enter or load an API key.")
        if provider == "Local GGUF":
            if not layer_state["base_url"]:
                raise ValueError(name + ": choose a local runtime executable.")
        elif not layer_state["base_url"]:
            raise ValueError(name + ": enter a base URL.")
        if not layer_state["model"]:
            if provider == "Local GGUF":
                raise ValueError(name + ": choose a local model file or Hugging Face repo ID.")
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
        def report_status(message):
            full_message = layer_state["name"] + ": " + message
            self.events.put(("status", full_message))
            self.events.put(("log", full_message))

        def report_notice(title, message):
            full_message = layer_state["name"] + ": " + message
            self.events.put(("notice", title, full_message))

        return ProviderClient(
            layer_state["provider"],
            layer_state["api_key"],
            layer_state["base_url"],
            layer_state["temperature"],
            layer_state["max_tokens"],
            status_callback=report_status,
            notice_callback=report_notice,
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
        provider = layer_state["provider"]
        if provider not in PROVIDERS:
            raise ValueError(name + ": choose a supported provider.")
        if provider == "Local GGUF":
            raise ValueError(name + ": use Models > Import local model file for this provider.")
        if provider_requires_api_key(provider) and not layer_state["api_key"]:
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
            messagebox.showinfo("Empty message", "Type a chat message first.")
            return
        start_index = self.chat_layer_index()
        try:
            layers = self.validate_chat(start_index)
        except Exception as exc:
            messagebox.showerror("Configuration problem", str(exc))
            return

        self.chat_history.append(
            {
                "role": "user",
                "layer_id": layers[start_index]["id"],
                "layer_name": layers[start_index]["name"],
                "content": message,
                "time": now_label(),
            }
        )
        self.render_chat_history()
        self.chat_input.delete("1.0", "end")

        global_input = self.input_text.get("1.0", "end-1c").strip()
        mode = self.chat_mode_var.get()
        history_snapshot = list(self.chat_history)
        self.set_busy(True)
        self.log("Chat fine-tuning from " + layers[start_index]["name"] + ".")
        self.worker = threading.Thread(
            target=self._chat_worker,
            args=(global_input, layers, start_index, message, history_snapshot, mode),
            daemon=True,
        )
        self.worker.start()

    def _chat_worker(self, global_input, layers, start_index, message, history_snapshot, mode):
        try:
            updated_names = []
            for index in range(start_index, len(layers)):
                layer = layers[index]
                self.events.put(("status", "Fine-tuning " + layer["name"]))
                prompt = build_chat_prompt(
                    global_input,
                    layers,
                    index,
                    message,
                    history_snapshot[:-1],
                    mode,
                )
                output = self.client_for_layer(layer).generate(layer["model"], prompt)
                output = strip_code_fences(output)

                if mode == "Append outputs":
                    block = make_addendum_block(layer["name"], output)
                    layers[index]["output"] = append_block(layer["output"], block)
                    self.events.put(("append_layer_output", layer["id"], block))
                else:
                    layers[index]["output"] = output
                    self.events.put(("set_layer_output", layer["id"], output))

                updated_names.append(layer["name"])
                self.events.put(("log", "Fine-tuned " + layer["name"] + "."))

            self.events.put(
                (
                    "chat_response",
                    {
                        "layer_id": layers[start_index]["id"],
                        "layer_name": layers[start_index]["name"],
                        "content": "Updated: " + ", ".join(updated_names),
                    },
                )
            )
            self.events.put(("done", "Ready"))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                event_type = event[0]

                if event_type == "models":
                    layer = self.layer_by_id(event[1])
                    if layer:
                        layer.set_model_options(event[2], selected=layer.model_var.get())
                        self.log(f"Loaded {len(layer.model_options)} models for {layer.display_name()}.")
                elif event_type == "set_layer_output":
                    layer = self.layer_by_id(event[1])
                    if layer:
                        layer.set_output(event[2])
                        self.schedule_flowchart_refresh()
                elif event_type == "append_layer_output":
                    layer = self.layer_by_id(event[1])
                    if layer:
                        layer.append_output(event[2])
                        self.schedule_flowchart_refresh()
                elif event_type == "chat_response":
                    response = event[1]
                    self.chat_history.append(
                        {
                            "role": "assistant",
                            "layer_id": response.get("layer_id", ""),
                            "layer_name": response.get("layer_name", ""),
                            "content": response.get("content", ""),
                            "time": now_label(),
                        }
                    )
                    self.render_chat_history()
                    self.log("Chat update complete.")
                elif event_type == "status":
                    self.status_var.set(event[1])
                elif event_type == "log":
                    self.log(event[1])
                elif event_type == "notice":
                    self.status_var.set(event[1])
                    self.log(event[2])
                    messagebox.showinfo(event[1], event[2])
                elif event_type == "done":
                    self.status_var.set(event[1])
                    self.set_busy(False)
                    self.autosave_session()
                    self.log("Finished.")
                elif event_type == "error":
                    self.status_var.set("Error")
                    self.set_busy(False)
                    self.log("Error: " + event[1])
                    messagebox.showerror("Request failed", event[1])
        except queue.Empty:
            pass

        self.after(100, self._process_events)

    def layer_by_id(self, layer_id):
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for widget in (
            self.add_layer_button,
            self.duplicate_layer_button,
            self.delete_layer_button,
            self.left_button,
            self.right_button,
            self.run_selected_button,
            self.run_all_button,
            self.send_chat_button,
        ):
            widget.configure(state=state)
        if busy:
            self.status_var.set("Working...")

    def clear_chat(self):
        self.chat_history = []
        self.render_chat_history()
        self.log("Chat cleared.")

    def render_chat_history(self):
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", "end")
        for item in self.chat_history:
            role = "You" if item.get("role") == "user" else "LayerGen"
            layer_name = item.get("layer_name", "")
            stamp = item.get("time", "")
            label = role
            if layer_name:
                label += " [" + layer_name + "]"
            if stamp:
                label += " " + stamp
            self.chat_text.insert("end", label + "\n" + item.get("content", "").rstrip() + "\n\n")
        self.chat_text.see("end")
        self.chat_text.configure(state="disabled")

    def log(self, message):
        if hasattr(self, "log_text"):
            self.log_text.insert("end", message.rstrip() + "\n")
            self.log_text.see("end")

    def save_layer_output(self, layer):
        output = layer.get_output()
        if not output:
            messagebox.showinfo("Nothing to save", "This layer has no output yet.")
            return
        extension = LANGUAGE_EXTENSIONS.get(layer.language_var.get(), ".txt")
        path = filedialog.asksaveasfilename(
            title="Save output",
            initialfile=layer.display_name().replace(" ", "_").lower() + extension,
            defaultextension=extension,
            filetypes=[
                ("Suggested type", "*" + extension),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            Path(path).write_text(output, encoding="utf-8")
            self.status_var.set("Output saved")
            self.log("Saved output to: " + path)
        except Exception as exc:
            messagebox.showerror("Could not save output", str(exc))

    def save_session_shortcut(self, event=None):
        self.save_session()
        return "break"

    def save_session_as_shortcut(self, event=None):
        self.save_session(save_as=True)
        return "break"

    def session_data(self):
        save_keys = self.save_keys_var.get()
        shared_keys = dict(self.shared_keys) if save_keys else {provider: "" for provider in PROVIDERS}
        return {
            "version": SESSION_VERSION,
            "app": APP_TITLE,
            "saved_at": now_label(),
            "save_keys": save_keys,
            "shared_keys": shared_keys,
            "global_input": self.input_text.get("1.0", "end-1c"),
            "chat_mode": self.chat_mode_var.get(),
            "chat_layer": self.chat_layer_var.get(),
            "layers": [layer.to_dict(save_keys=save_keys) for layer in self.layers],
            "chat_history": self.chat_history,
        }

    def save_session(self, save_as=False, silent=False):
        path = self.session_path
        if save_as or not path:
            default_name = "layergen_session_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            path = filedialog.asksaveasfilename(
                title="Save session",
                initialfile=default_name + ".json",
                defaultextension=".json",
                filetypes=[
                    ("LayerGen sessions", "*.json"),
                    ("All files", "*.*"),
                ],
            )
            if not path:
                return False
        try:
            Path(path).write_text(json.dumps(self.session_data(), indent=2), encoding="utf-8")
            self.session_path = path
            if not silent:
                self.status_var.set("Saved session")
                self.log("Saved session to: " + path)
            return True
        except Exception as exc:
            if not silent:
                messagebox.showerror("Could not save session", str(exc))
            return False

    def autosave_session(self):
        if self.session_path:
            self.save_session(silent=True)

    def load_session(self):
        path = filedialog.askopenfilename(
            title="Load session",
            filetypes=[
                ("LayerGen sessions", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.clear_project(confirm=False)

            self.save_keys_var.set(bool(data.get("save_keys", False)))
            loaded_shared = data.get("shared_keys", {})
            self.shared_keys = {}
            for provider in PROVIDERS:
                self.shared_keys[provider] = loaded_shared.get(provider) or default_api_key(provider)

            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", data.get("global_input", ""))
            self.chat_mode_var.set(data.get("chat_mode", "Replace outputs"))

            for layer_data in data.get("layers", []):
                if not layer_data.get("api_key") and layer_data.get("key_scope") == "Shared provider key":
                    layer_data["api_key"] = self.shared_keys.get(layer_data.get("provider", "Gemini"), "")
                self.add_layer(layer_data)

            self.chat_history = data.get("chat_history", [])
            self.render_chat_history()
            self.refresh_layer_titles()
            saved_chat_layer = data.get("chat_layer", "")
            if saved_chat_layer in self.chat_labels():
                self.chat_layer_var.set(saved_chat_layer)
            self.session_path = path
            self.status_var.set("Session loaded")
            self.log("Loaded session from: " + path)
        except Exception as exc:
            messagebox.showerror("Could not load session", str(exc))

    def clear_project(self, confirm=True):
        if confirm and not messagebox.askyesno("Clear project", "Clear all layers and chat?"):
            return False
        for layer in list(self.layers):
            self.layers_notebook.forget(layer.frame)
        self.layers = []
        self.chat_history = []
        self.input_text.delete("1.0", "end")
        self.render_chat_history()
        self.refresh_chat_layers()
        self.schedule_flowchart_refresh()
        return True

    def new_project(self):
        if self.layers or self.chat_history or self.input_text.get("1.0", "end-1c").strip():
            if not self.save_session(save_as=True):
                return
        self.clear_project(confirm=False)
        self.session_path = None
        self.status_var.set("New project ready")
        self.log("Started a blank project.")


def main():
    app = LayerGenApp()
    app.mainloop()


if __name__ == "__main__":
    main()
