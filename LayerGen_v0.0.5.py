# -*- coding: utf-8 -*-
"""
LayerGen

A single-file, plain GUI for building configurable chained AI layers.

Run with:
    python LayerGen.py

This file uses only Python's standard library.
"""

import json
import base64
import mimetypes
import os
import queue
import re
import subprocess
import sys
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
SESSION_VERSION = 8
ANTHROPIC_VERSION = "2023-06-01"

PROVIDERS = (
    "Gemini",
    "OpenAI-compatible",
    "Anthropic",
    "Ollama",
    "Hugging Face",
    "Transformers",
)
DEFAULT_BASE_URLS = {
    "Gemini": "https://generativelanguage.googleapis.com/v1beta",
    "OpenAI-compatible": "https://api.openai.com/v1",
    "Anthropic": "https://api.anthropic.com/v1",
    "Ollama": "http://localhost:11434",
    "Hugging Face": "https://router.huggingface.co/v1",
    "Transformers": "local",
}
HUGGINGFACE_HUB_MODELS_URL = "https://huggingface.co/api/models"
HUGGINGFACE_SEARCH_LIMIT = 300
HUGGINGFACE_SEARCH_PER_TASK_LIMIT = 125
HUGGINGFACE_SEARCH_TASKS = (
    ("Chat / code / text", ("conversational", "text-generation")),
    ("Vision / image input", ("image-text-to-text",)),
    ("Any compatible", ("conversational", "text-generation", "image-text-to-text")),
)
HUGGINGFACE_DEFAULT_SEARCH_TASK = HUGGINGFACE_SEARCH_TASKS[0][0]
LOCAL_MODEL_SOURCES = ("Ollama library", "Hugging Face GGUF", "Hugging Face Transformers")
LOCAL_MODEL_DEFAULT_SOURCE = LOCAL_MODEL_SOURCES[0]
LOCAL_MODEL_SEARCH_LIMIT = 120
OLLAMA_LIBRARY_MODELS = (
    "llama3.3",
    "llama3.2",
    "llama3.2:1b",
    "llama3.2:3b",
    "llama3.1",
    "llama3.1:8b",
    "llama3.1:70b",
    "qwen3",
    "qwen3:0.6b",
    "qwen3:1.7b",
    "qwen3:4b",
    "qwen3:8b",
    "qwen3:14b",
    "qwen3:32b",
    "qwen2.5",
    "qwen2.5:0.5b",
    "qwen2.5:1.5b",
    "qwen2.5:3b",
    "qwen2.5:7b",
    "qwen2.5:14b",
    "qwen2.5:32b",
    "qwen2.5-coder",
    "qwen2.5-coder:1.5b",
    "qwen2.5-coder:3b",
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "qwen2.5-coder:32b",
    "deepseek-r1",
    "deepseek-r1:1.5b",
    "deepseek-r1:7b",
    "deepseek-r1:8b",
    "deepseek-r1:14b",
    "deepseek-r1:32b",
    "deepseek-r1:70b",
    "gemma3",
    "gemma3:1b",
    "gemma3:4b",
    "gemma3:12b",
    "gemma3:27b",
    "gemma2",
    "gemma2:2b",
    "gemma2:9b",
    "gemma2:27b",
    "mistral",
    "mistral-nemo",
    "mixtral",
    "mixtral:8x7b",
    "codellama",
    "codellama:7b",
    "codellama:13b",
    "codellama:34b",
    "codegemma",
    "codegemma:2b",
    "codegemma:7b",
    "starcoder2",
    "starcoder2:3b",
    "starcoder2:7b",
    "starcoder2:15b",
    "phi4",
    "phi4-mini",
    "phi3",
    "phi3:mini",
    "phi3:medium",
    "granite3.3",
    "granite3.2",
    "command-r",
    "command-r-plus",
    "llava",
    "llava:7b",
    "llava:13b",
    "minicpm-v",
    "moondream",
    "bakllava",
)
PROVIDER_ENV_KEYS = {
    "Gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "OpenAI-compatible": ("OPENAI_API_KEY", "API_KEY"),
    "Anthropic": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
    "Ollama": (),
    "Hugging Face": (
        "HF_TOKEN",
        "HUGGINGFACE_API_KEY",
        "HUGGINGFACE_TOKEN",
        "HUGGINGFACEHUB_API_TOKEN",
    ),
    "Transformers": (
        "HF_TOKEN",
        "HUGGINGFACE_API_KEY",
        "HUGGINGFACE_TOKEN",
        "HUGGINGFACEHUB_API_TOKEN",
    ),
}
KEY_SCOPES = ("Shared provider key", "Layer-specific key")
CHAT_MODES = ("Replace outputs", "Append outputs")
MAX_TEXT_ATTACHMENT_CHARS = 60000
MAX_INLINE_ATTACHMENT_BYTES = 15 * 1024 * 1024
ANTHROPIC_MAX_IMAGE_BYTES = 3750000

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
RICH_HEADING1_FONT = ("Segoe UI Semibold", 15)
RICH_HEADING2_FONT = ("Segoe UI Semibold", 13)
RICH_HEADING3_FONT = ("Segoe UI Semibold", 11)
RICH_BOLD_FONT = ("Segoe UI Semibold", 10)
RICH_ITALIC_FONT = ("Segoe UI", 10, "italic")
RICH_BOLD_ITALIC_FONT = ("Segoe UI Semibold", 10, "italic")
RICH_MATH_FONT = ("Cambria Math", 10)

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


TEXT_EXTENSIONS = {
    ".bat",
    ".c",
    ".cfg",
    ".conf",
    ".cpp",
    ".cs",
    ".css",
    ".csv",
    ".env",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".log",
    ".md",
    ".php",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def now_label():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_id():
    return uuid.uuid4().hex[:12]


def guess_mime_type(name):
    mime_type, _ = mimetypes.guess_type(name)
    if mime_type:
        return mime_type
    suffix = Path(name).suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return "text/plain"
    return "application/octet-stream"


def is_text_attachment(attachment):
    mime_type = attachment.get("mime_type", "")
    if mime_type.startswith("text/"):
        return True
    suffix = Path(attachment.get("name") or attachment.get("path") or "").suffix.lower()
    return suffix in TEXT_EXTENSIONS


def is_image_attachment(attachment):
    return attachment.get("mime_type", "").startswith("image/")


def is_audio_attachment(attachment):
    return attachment.get("mime_type", "").startswith("audio/")


def is_video_attachment(attachment):
    return attachment.get("mime_type", "").startswith("video/")


def is_pdf_attachment(attachment):
    return attachment.get("mime_type", "") == "application/pdf"


def is_local_attachment(attachment):
    return attachment.get("kind") == "file" and bool(attachment.get("path"))


def is_url_attachment(attachment):
    return attachment.get("kind") == "url" and bool(attachment.get("url"))


def format_file_size(size):
    try:
        size = int(size)
    except (TypeError, ValueError):
        return ""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def normalize_attachment(attachment):
    if not isinstance(attachment, dict):
        return None
    kind = attachment.get("kind", "file")
    if kind not in ("file", "url"):
        kind = "file"
    path = attachment.get("path", "")
    url = attachment.get("url", "")
    name = attachment.get("name", "")
    if not name:
        source = url or path
        parsed = urllib.parse.urlparse(source)
        name = Path(parsed.path).name or source or "attachment"
    mime_type = attachment.get("mime_type") or guess_mime_type(name)
    size = attachment.get("size", 0)
    if kind == "file" and path:
        try:
            size = Path(path).stat().st_size
        except OSError:
            pass
    return {
        "id": attachment.get("id") or make_id(),
        "kind": kind,
        "path": path,
        "url": url,
        "name": name,
        "mime_type": mime_type,
        "size": size,
    }


def normalize_attachments(attachments):
    normalized = []
    for attachment in attachments or []:
        item = normalize_attachment(attachment)
        if item:
            normalized.append(item)
    return normalized


def make_file_attachment(path):
    path_obj = Path(path)
    return normalize_attachment(
        {
            "kind": "file",
            "path": str(path_obj),
            "name": path_obj.name,
            "mime_type": guess_mime_type(path_obj.name),
        }
    )


def make_url_attachment(url):
    url = url.strip()
    parsed = urllib.parse.urlparse(url)
    name = Path(parsed.path).name or parsed.netloc or "url"
    return normalize_attachment(
        {
            "kind": "url",
            "url": url,
            "name": name,
            "mime_type": guess_mime_type(name),
        }
    )


def attachment_label(attachment):
    name = attachment.get("name", "attachment")
    mime_type = attachment.get("mime_type", "application/octet-stream")
    size = format_file_size(attachment.get("size"))
    if size:
        return f"{name} ({mime_type}, {size})"
    return f"{name} ({mime_type})"


def attachments_summary(attachments):
    attachments = attachments or []
    if not attachments:
        return "No attachments"
    names = [attachment.get("name", "attachment") for attachment in attachments[:3]]
    label = ", ".join(names)
    if len(attachments) > 3:
        label += f", +{len(attachments) - 3}"
    return f"{len(attachments)} attachment{'s' if len(attachments) != 1 else ''}: {label}"


def read_local_text_attachment(attachment):
    path = Path(attachment.get("path", ""))
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return f"[Could not read {attachment_label(attachment)}: {exc}]"

    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            pass
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    truncated = False
    if len(text) > MAX_TEXT_ATTACHMENT_CHARS:
        text = text[:MAX_TEXT_ATTACHMENT_CHARS]
        truncated = True
    suffix = "\n[Attachment truncated.]" if truncated else ""
    return text.rstrip() + suffix


def attachment_prompt_context(attachments, title):
    attachments = attachments or []
    if not attachments:
        return ""

    blocks = [title + ":"]
    for attachment in attachments:
        label = attachment_label(attachment)
        if is_text_attachment(attachment) and is_local_attachment(attachment):
            blocks.append(f"\n--- {label} ---\n{read_local_text_attachment(attachment)}")
        elif is_text_attachment(attachment) and is_url_attachment(attachment):
            blocks.append(f"\n--- {label} ---\nURL: {attachment.get('url', '')}")
        elif is_url_attachment(attachment):
            blocks.append(f"\nAttached URL: {label}\n{attachment.get('url', '')}")
        else:
            blocks.append(f"\nAttached file: {label}")
    return "\n".join(blocks).strip()


def append_attachment_context(text, attachments, title):
    context = attachment_prompt_context(attachments, title)
    text = text.strip()
    if not context:
        return text
    if not text:
        return context
    return text + "\n\n" + context


def attachment_brief_context(attachments, title):
    attachments = attachments or []
    if not attachments:
        return ""
    lines = [title + ":"]
    for attachment in attachments:
        if is_url_attachment(attachment):
            lines.append("- " + attachment_label(attachment) + ": " + attachment.get("url", ""))
        else:
            lines.append("- " + attachment_label(attachment))
    return "\n".join(lines)


def append_attachment_summary(text, attachments, title):
    summary = attachment_brief_context(attachments, title)
    text = text.strip()
    if not summary:
        return text
    if not text:
        return summary
    return text + "\n\n" + summary


def read_local_attachment_b64(attachment, max_bytes=MAX_INLINE_ATTACHMENT_BYTES):
    path = Path(attachment.get("path", ""))
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise RuntimeError(f"Could not read {attachment_label(attachment)}: {exc}")
    if size > max_bytes:
        raise RuntimeError(
            f"{attachment.get('name', 'Attachment')} is too large to send inline "
            f"({format_file_size(size)})."
        )
    return base64.b64encode(path.read_bytes()).decode("ascii")


def attachment_data_url(attachment):
    data = read_local_attachment_b64(attachment)
    return "data:" + attachment.get("mime_type", "application/octet-stream") + ";base64," + data


def attachment_audio_format(attachment):
    suffix = Path(attachment.get("name", "")).suffix.lower()
    if suffix == ".mp3":
        return "mp3"
    if suffix == ".wav":
        return "wav"
    return ""


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


def huggingface_task_labels():
    return [label for label, _tags in HUGGINGFACE_SEARCH_TASKS]


def huggingface_task_tags(label):
    for task_label, tags in HUGGINGFACE_SEARCH_TASKS:
        if task_label == label:
            return tags
    return HUGGINGFACE_SEARCH_TASKS[0][1]


def extract_huggingface_model_id(item):
    if isinstance(item, str):
        model_id = item
    elif isinstance(item, dict):
        model_id = item.get("id") or item.get("modelId") or item.get("name")
    else:
        return ""
    model_id = normalize_huggingface_repo_id(str(model_id))
    if is_huggingface_repo_id(model_id):
        return model_id
    return ""


def huggingface_model_matches_search(model_id, query):
    query = query.strip().lower()
    if not query:
        return True
    return query in model_id.lower()


def append_unique_model(models, seen, model_id, query=""):
    model_id = normalize_huggingface_repo_id(model_id)
    if not model_id or model_id in seen:
        return
    if not is_huggingface_repo_id(model_id):
        return
    if not huggingface_model_matches_search(model_id, query):
        return
    seen.add(model_id)
    models.append(model_id)


def query_url(base_url, params):
    clean_params = {
        key: value
        for key, value in params.items()
        if value is not None and str(value) != ""
    }
    if not clean_params:
        return base_url
    return base_url + "?" + urllib.parse.urlencode(clean_params)


def normalize_ollama_model_name(value):
    return value.strip().strip('"').strip("'").strip()


def is_ollama_model_name(value):
    model_name = normalize_ollama_model_name(value)
    if not model_name:
        return False
    if model_name.lower().startswith(("http://", "https://")):
        return False
    return not any(char.isspace() for char in model_name)


def model_matches_query(model_name, query):
    query = query.strip().lower()
    if not query:
        return True
    return query in model_name.lower()


def local_model_source_labels():
    return list(LOCAL_MODEL_SOURCES)


def list_ollama_library_models(query="", limit=LOCAL_MODEL_SEARCH_LIMIT):
    results = [
        model
        for model in OLLAMA_LIBRARY_MODELS
        if model_matches_query(model, query)
    ]
    return sorted(set(results), key=model_sort_key)[:limit]


def list_huggingface_gguf_models(query="", api_key="", limit=LOCAL_MODEL_SEARCH_LIMIT):
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    params = {
        "library": "gguf",
        "sort": "downloads",
        "direction": "-1",
        "limit": str(limit),
    }
    if query.strip():
        params["search"] = query.strip()
    data = request_json(
        query_url(HUGGINGFACE_HUB_MODELS_URL, params),
        headers=headers,
        timeout=60,
    )
    models = []
    seen = set()
    if isinstance(data, list):
        for item in data:
            model_id = extract_huggingface_model_id(item)
            if not model_id or model_id in seen:
                continue
            seen.add(model_id)
            models.append("hf.co/" + model_id)
    return sorted(models, key=model_sort_key)[:limit]


def list_huggingface_transformers_models(query="", api_key="", limit=LOCAL_MODEL_SEARCH_LIMIT):
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    params = {
        "pipeline_tag": "text-generation",
        "sort": "downloads",
        "direction": "-1",
        "limit": str(limit),
    }
    if query.strip():
        params["search"] = query.strip()
    data = request_json(
        query_url(HUGGINGFACE_HUB_MODELS_URL, params),
        headers=headers,
        timeout=60,
    )
    models = []
    seen = set()
    if isinstance(data, list):
        for item in data:
            model_id = extract_huggingface_model_id(item)
            if not model_id or model_id in seen:
                continue
            lowered = model_id.lower()
            if "gguf" in lowered:
                continue
            seen.add(model_id)
            models.append(model_id)
    return sorted(models, key=model_sort_key)[:limit]


def list_local_download_models(
    query="",
    source=LOCAL_MODEL_DEFAULT_SOURCE,
    api_key="",
    limit=LOCAL_MODEL_SEARCH_LIMIT,
):
    if source == "Hugging Face GGUF":
        return list_huggingface_gguf_models(query=query, api_key=api_key, limit=limit)
    if source == "Hugging Face Transformers":
        return list_huggingface_transformers_models(
            query=query,
            api_key=api_key,
            limit=limit,
        )
    return list_ollama_library_models(query=query, limit=limit)


def normalize_provider_name(provider):
    if provider not in PROVIDERS and str(provider).startswith("Local "):
        return "Hugging Face"
    return provider


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


def pull_ollama_model(base_url, model_name, status_callback=None):
    model_name = normalize_ollama_model_name(model_name)
    if not is_ollama_model_name(model_name):
        raise ValueError("Enter an Ollama model name like qwen2.5-coder:7b or hf.co/author/model-GGUF.")

    request_headers = {"Content-Type": "application/json"}
    payload = {"model": model_name, "stream": True}
    request = urllib.request.Request(
        join_url(base_url, "api/pull"),
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )

    last_emit = 0.0
    last_status = ""
    try:
        with urllib.request.urlopen(request, timeout=7200) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("error"):
                    raise RuntimeError(data["error"])
                status = data.get("status", "")
                total = data.get("total")
                completed = data.get("completed")
                if total and completed is not None:
                    percent = int(max(0, min(100, (completed / total) * 100)))
                    status = f"{status} {percent}%"
                if status:
                    last_status = status
                    now = time.monotonic()
                    if status_callback and (now - last_emit > 0.5 or "success" in status.lower()):
                        status_callback(status)
                        last_emit = now
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama download failed with HTTP {exc.code}: {clean_error(details)}")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Could not reach Ollama at "
            + normalize_base_url(base_url)
            + ". Start Ollama, then try again. Details: "
            + str(exc.reason)
        )

    if status_callback:
        status_callback(last_status or "success")
    return last_status or "success"


TRANSFORMERS_HELPER_SCRIPT = r"""
import json
import os
import sys

payload = json.loads(sys.stdin.read() or "{}")
action = payload.get("action", "")
model_name = payload.get("model_name", "")
token = payload.get("api_key") or None

try:
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ModuleNotFoundError as exc:
    print(json.dumps({"error": "missing_dependencies", "missing": exc.name}))
    sys.exit(2)

if token:
    os.environ["HF_TOKEN"] = token
    os.environ["HUGGING_FACE_HUB_TOKEN"] = token

def load_tokenizer():
    return AutoTokenizer.from_pretrained(
        model_name,
        token=token,
        trust_remote_code=True,
    )

def load_model():
    return AutoModelForCausalLM.from_pretrained(
        model_name,
        token=token,
        trust_remote_code=True,
        torch_dtype="auto",
    )

try:
    if action == "download":
        snapshot_download(
            repo_id=model_name,
            token=token,
            allow_patterns=[
                "*.json",
                "*.safetensors",
                "*.bin",
                "*.model",
                "*.txt",
                "*.py",
                "*.tiktoken",
                "*.jinja",
                "tokenizer*",
                "generation_config.*",
                "special_tokens_map.*",
                "vocab.*",
                "merges.*",
            ],
        )
        print(json.dumps({"status": "downloaded"}))
        sys.exit(0)

    tokenizer = load_tokenizer()
    model = load_model()

    prompt = payload.get("prompt", "")
    max_tokens = int(payload.get("max_tokens") or 512)
    temperature = float(payload.get("temperature") or 0.0)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    messages = [{"role": "user", "content": prompt}]
    try:
        input_ids = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        )
    except Exception:
        input_ids = tokenizer(prompt, return_tensors="pt").input_ids

    input_ids = input_ids.to(device)
    generate_kwargs = {
        "max_new_tokens": max_tokens,
        "do_sample": temperature > 0,
    }
    if temperature > 0:
        generate_kwargs["temperature"] = temperature
    if tokenizer.eos_token_id is not None:
        generate_kwargs["eos_token_id"] = tokenizer.eos_token_id
        generate_kwargs["pad_token_id"] = tokenizer.eos_token_id

    with torch.no_grad():
        output_ids = model.generate(input_ids, **generate_kwargs)

    new_tokens = output_ids[0][input_ids.shape[-1]:]
    text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    print(json.dumps({"text": text}))
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
    sys.exit(1)
"""


def transformers_install_message():
    return (
        "Local Transformers support needs PyTorch and Hugging Face Transformers. "
        "Install them for the Python that runs LayerGen:\n\n"
        + sys.executable
        + " -m pip install torch transformers accelerate safetensors sentencepiece protobuf"
    )


def run_transformers_helper(payload, timeout=7200):
    env = os.environ.copy()
    api_key = payload.get("api_key", "")
    if api_key:
        env["HF_TOKEN"] = api_key
        env["HUGGING_FACE_HUB_TOKEN"] = api_key

    process = subprocess.run(
        [sys.executable, "-c", TRANSFORMERS_HELPER_SCRIPT],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )

    lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    data = {}
    if lines:
        try:
            data = json.loads(lines[-1])
        except json.JSONDecodeError:
            data = {}

    if data.get("error") == "missing_dependencies":
        raise RuntimeError(transformers_install_message())
    if process.returncode != 0 or data.get("error"):
        details = data.get("error") or process.stderr.strip() or process.stdout.strip()
        raise RuntimeError("Transformers failed: " + (details or "No details returned."))
    return data


def download_transformers_model(model_name, api_key="", status_callback=None):
    model_name = normalize_huggingface_repo_id(model_name)
    if not is_huggingface_repo_id(model_name):
        raise ValueError("Use a Hugging Face repo ID like author/model.")
    if status_callback:
        status_callback("Downloading normal Hugging Face model with Transformers...")
    run_transformers_helper(
        {
            "action": "download",
            "model_name": model_name,
            "api_key": api_key,
        }
    )
    if status_callback:
        status_callback("Downloaded")


def generate_with_transformers(model_name, prompt, api_key="", temperature=0.0, max_tokens=512):
    model_name = normalize_huggingface_repo_id(model_name)
    if not is_huggingface_repo_id(model_name):
        raise ValueError("Use a Hugging Face repo ID like author/model.")
    data = run_transformers_helper(
        {
            "action": "generate",
            "model_name": model_name,
            "prompt": prompt,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    )
    text = data.get("text", "")
    if not text:
        raise RuntimeError("Transformers did not return text.")
    return text


def list_huggingface_models(
    api_key="",
    base_url=DEFAULT_BASE_URLS["Hugging Face"],
    query="",
    task_label=HUGGINGFACE_DEFAULT_SEARCH_TASK,
    limit=HUGGINGFACE_SEARCH_LIMIT,
):
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    query = query.strip()
    models = []
    seen = set()
    errors = []

    if base_url and task_label != "Vision / image input":
        router_limit = min(limit, HUGGINGFACE_SEARCH_PER_TASK_LIMIT)
        try:
            data = request_json(
                join_url(base_url, "models"),
                headers=headers,
                timeout=60,
            )
            for item in data.get("data", []):
                append_unique_model(
                    models,
                    seen,
                    extract_huggingface_model_id(item),
                    query=query,
                )
                if len(models) >= router_limit:
                    break
        except RuntimeError as exc:
            errors.append(str(exc))

    for task_tag in huggingface_task_tags(task_label):
        if len(models) >= limit:
            return sorted(models, key=model_sort_key)
        params = {
            "inference_provider": "all",
            "pipeline_tag": task_tag,
            "sort": "downloads",
            "direction": "-1",
            "limit": str(HUGGINGFACE_SEARCH_PER_TASK_LIMIT),
        }
        if query:
            params["search"] = query
        try:
            data = request_json(
                query_url(HUGGINGFACE_HUB_MODELS_URL, params),
                headers=headers,
                timeout=60,
            )
        except RuntimeError as exc:
            errors.append(str(exc))
            continue

        if isinstance(data, list):
            for item in data:
                append_unique_model(
                    models,
                    seen,
                    extract_huggingface_model_id(item),
                    query=query,
                )
                if len(models) >= limit:
                    return sorted(models, key=model_sort_key)

    if not models and errors:
        raise RuntimeError("Could not load Hugging Face models: " + errors[-1])
    return sorted(models, key=model_sort_key)


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


def extract_text_value(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            text = extract_text_value(item)
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    if isinstance(value, dict):
        for key in ("text", "output_text", "content", "value", "generated_text"):
            text = extract_text_value(value.get(key))
            if text:
                return text
    return ""


def extract_text_from_openai_response(data):
    choices = data.get("choices", [])
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") or {}
        delta = choice.get("delta") or {}
        candidates = (
            message.get("content"),
            message.get("text"),
            message.get("output_text"),
            choice.get("text"),
            delta.get("content"),
            message.get("reasoning_content"),
            message.get("reasoning"),
        )
        for candidate in candidates:
            text = extract_text_value(candidate)
            if text:
                return text

    for candidate in (
        data.get("output_text"),
        data.get("generated_text"),
        data.get("text"),
        data.get("content"),
    ):
        text = extract_text_value(candidate)
        if text:
            return text

    if not choices:
        raise RuntimeError("The provider response did not include any choices.")
    raise RuntimeError("The provider response did not include text content.")


def extract_text_from_openai_responses_response(data):
    for candidate in (
        data.get("output_text"),
        data.get("text"),
        data.get("generated_text"),
        data.get("content"),
    ):
        text = extract_text_value(candidate)
        if text:
            return text

    parts = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for candidate in (
            item.get("content"),
            item.get("text"),
            item.get("output_text"),
            item.get("generated_text"),
        ):
            text = extract_text_value(candidate)
            if text:
                parts.append(text)

    if parts:
        return "\n".join(parts).strip()
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
    return provider in ("Gemini", "Anthropic", "Hugging Face")


def api_key_required_message(provider):
    if provider == "Hugging Face":
        return "Enter a Hugging Face token in Settings > API key before running."
    return "Enter or load an API key."


def huggingface_model_not_supported_message(model_name):
    lowered = model_name.lower().split(":", 1)[0]
    if "gemma-4" in lowered:
        return (
            "Hugging Face found the Gemma 4 repo, but the selected router route is "
            "not serving it for this request. Gemma 4 models are tagged as multimodal "
            "Any-to-Any/Image-Text-to-Text on Hugging Face, so provider support can "
            "differ from normal text chat models. Try Models > Search Hugging Face "
            "models and choose the Vision / image input type."
        )
    if lowered in ("qwen/qwen2-7b", "qwen/qwen2-7b-instruct"):
        return (
            "Hugging Face found the model, but your selected provider route is not "
            "serving it for chat. Use Models > Search Hugging Face models and search "
            "for Qwen instruct models."
        )
    if "qwen" in lowered and "coder" in lowered:
        return (
            "Hugging Face found the model, but your selected provider route is not "
            "serving it for chat. Use Models > Search Hugging Face models and search "
            "for Qwen coder models."
        )
    return (
        "Hugging Face found the model, but no enabled Inference Provider is serving "
        "it for this request. Use Models > Search Hugging Face models to choose from "
        "served models."
    )


def huggingface_forbidden_message(model_name):
    return (
        "Hugging Face returned 403 Forbidden for " + model_name + ". This usually means "
        "your token or account is not allowed to use that provider route. In Hugging Face, "
        "check that your token has Inference Providers permission, the provider is enabled "
        "in Inference Providers settings, and your account has credits or billing set up. "
        "You can also try changing the model suffix to :fastest so Hugging Face picks an "
        "available route."
    )


def huggingface_uses_text_content_parts(model_name):
    lowered = model_name.lower().split(":", 1)[0]
    multimodal_markers = ("gemma-4", "-vl-", "vision", "image-text", "smolvlm")
    return any(marker in lowered for marker in multimodal_markers)


def huggingface_is_not_chat_error(error_text):
    lowered = error_text.lower()
    markers = (
        "isn't a chat model",
        "is not a chat model",
        "not a chat model",
        "not supported for chat",
        "chat model",
    )
    return any(marker in lowered for marker in markers)


def provider_no_text_content_error(error_text):
    lowered = error_text.lower()
    markers = (
        "did not include text content",
        "did not include any choices",
        "no readable text",
        "no text content",
    )
    return any(marker in lowered for marker in markers)


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
        self.provider = normalize_provider_name(provider)
        self.api_key = api_key.strip()
        self.base_url = normalize_base_url(base_url)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.status_callback = status_callback
        self.notice_callback = notice_callback

        if self.provider not in PROVIDERS:
            raise ValueError("Choose a supported provider.")
        if provider_requires_api_key(self.provider) and not self.api_key:
            raise ValueError(api_key_required_message(self.provider))
        if not self.base_url:
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
        if self.provider == "Hugging Face":
            return self._list_huggingface_models()
        if self.provider == "Transformers":
            return list_huggingface_transformers_models(api_key=self.api_key)
        return self._list_openai_compatible_models()

    def generate(self, model_name, prompt, attachments=None):
        model_name = model_name.strip()
        attachments = normalize_attachments(attachments)
        if not model_name:
            raise ValueError("Choose a model.")

        if self.provider == "Gemini":
            return self._generate_gemini(model_name, prompt, attachments)
        if self.provider == "Anthropic":
            return self._generate_anthropic(model_name, prompt, attachments)
        if self.provider == "Ollama":
            return self._generate_ollama(model_name, prompt)
        if self.provider == "Hugging Face":
            return self._generate_huggingface(model_name, prompt, attachments)
        if self.provider == "Transformers":
            return self._generate_transformers(model_name, prompt)
        return self._generate_openai_compatible(model_name, prompt, attachments)

    def _openai_content(self, prompt, attachments=None, force_parts=False):
        attachments = normalize_attachments(attachments)
        if not attachments and not force_parts:
            return prompt

        parts = []
        for attachment in attachments:
            if is_image_attachment(attachment):
                if is_url_attachment(attachment):
                    image_url = attachment.get("url", "")
                elif is_local_attachment(attachment):
                    image_url = attachment_data_url(attachment)
                else:
                    continue
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    }
                )
            elif is_audio_attachment(attachment) and is_local_attachment(attachment):
                audio_format = attachment_audio_format(attachment)
                if audio_format:
                    parts.append(
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": read_local_attachment_b64(attachment),
                                "format": audio_format,
                            },
                        }
                    )

        if not parts and not force_parts:
            return prompt
        parts.append({"type": "text", "text": prompt})
        return parts

    def _responses_input(self, prompt, attachments=None):
        attachments = normalize_attachments(attachments)
        if not attachments:
            return prompt

        content = []
        for attachment in attachments:
            if is_image_attachment(attachment):
                if is_url_attachment(attachment):
                    image_url = attachment.get("url", "")
                elif is_local_attachment(attachment):
                    image_url = attachment_data_url(attachment)
                else:
                    continue
                content.append({"type": "input_image", "image_url": image_url})
        if not content:
            return prompt
        content.append({"type": "input_text", "text": prompt})
        return [{"role": "user", "content": content}]

    def _gemini_parts(self, prompt, attachments=None):
        parts = []
        for attachment in normalize_attachments(attachments):
            if not is_local_attachment(attachment):
                continue
            if not (
                is_image_attachment(attachment)
                or is_audio_attachment(attachment)
                or is_video_attachment(attachment)
                or is_pdf_attachment(attachment)
            ):
                continue
            parts.append(
                {
                    "inline_data": {
                        "mime_type": attachment.get("mime_type", "application/octet-stream"),
                        "data": read_local_attachment_b64(attachment),
                    }
                }
            )
        parts.append({"text": prompt})
        return parts

    def _anthropic_content(self, prompt, attachments=None):
        blocks = []
        for attachment in normalize_attachments(attachments):
            if is_image_attachment(attachment):
                if is_url_attachment(attachment):
                    blocks.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "url",
                                "url": attachment.get("url", ""),
                            },
                        }
                    )
                elif is_local_attachment(attachment):
                    blocks.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": attachment.get("mime_type", "image/png"),
                                "data": read_local_attachment_b64(
                                    attachment,
                                    max_bytes=ANTHROPIC_MAX_IMAGE_BYTES,
                                ),
                            },
                        }
                    )
            elif is_pdf_attachment(attachment):
                if is_url_attachment(attachment):
                    blocks.append(
                        {
                            "type": "document",
                            "source": {
                                "type": "url",
                                "url": attachment.get("url", ""),
                            },
                        }
                    )
                elif is_local_attachment(attachment):
                    blocks.append(
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": read_local_attachment_b64(attachment),
                            },
                        }
                    )

        blocks.append({"type": "text", "text": prompt})
        return blocks

    def _list_gemini_models(self):
        params = urllib.parse.urlencode({"key": self.api_key})
        data = request_json(join_url(self.base_url, "models") + "?" + params)
        model_names = []
        for model in data.get("models", []):
            methods = model.get("supportedGenerationMethods", [])
            if "generateContent" in methods and model.get("name"):
                model_names.append(model["name"])
        return sorted(set(model_names), key=model_sort_key)

    def _generate_gemini(self, model_name, prompt, attachments=None):
        model_path = urllib.parse.quote(model_name, safe="/")
        params = urllib.parse.urlencode({"key": self.api_key})
        url = join_url(self.base_url, model_path + ":generateContent") + "?" + params
        payload = {
            "contents": [{"role": "user", "parts": self._gemini_parts(prompt, attachments)}],
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

    def _generate_openai_compatible(self, model_name, prompt, attachments=None):
        headers = {}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": self._openai_content(prompt, attachments)}
            ],
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

    def _huggingface_headers(self):
        if not self.api_key:
            return {}
        return {"Authorization": "Bearer " + self.api_key}

    def _list_huggingface_models(
        self,
        query="",
        task_label=HUGGINGFACE_DEFAULT_SEARCH_TASK,
        limit=HUGGINGFACE_SEARCH_LIMIT,
    ):
        return list_huggingface_models(
            api_key=self.api_key,
            base_url=self.base_url,
            query=query,
            task_label=task_label,
            limit=limit,
        )

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

    def _generate_transformers(self, model_name, prompt):
        self._report_status("Running local Transformers model.")
        return generate_with_transformers(
            model_name,
            prompt,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def _generate_huggingface(self, model_name, prompt, attachments=None):
        headers = {"Authorization": "Bearer " + self.api_key}
        use_parts = huggingface_uses_text_content_parts(model_name)
        try:
            data = self._request_huggingface_chat(
                model_name,
                prompt,
                headers,
                attachments,
                use_text_content_parts=use_parts,
            )
            return extract_text_from_openai_response(data)
        except RuntimeError as exc:
            error_text = str(exc)
            if (
                huggingface_is_not_chat_error(error_text)
                or provider_no_text_content_error(error_text)
            ) and not use_parts:
                if provider_no_text_content_error(error_text):
                    self._report_status(
                        "Chat response had no readable text; retrying with typed text content."
                    )
                else:
                    self._report_status(
                        "Chat route rejected plain text; retrying with typed text content."
                    )
                try:
                    data = self._request_huggingface_chat(
                        model_name,
                        prompt,
                        headers,
                        attachments,
                        use_text_content_parts=True,
                    )
                    return extract_text_from_openai_response(data)
                except RuntimeError as retry_exc:
                    error_text = str(retry_exc)
                    exc = retry_exc
            if huggingface_is_not_chat_error(error_text) or provider_no_text_content_error(
                error_text
            ):
                if provider_no_text_content_error(error_text):
                    self._report_status(
                        "Chat response had no readable text; trying Hugging Face Responses API."
                    )
                else:
                    self._report_status(
                        "Chat route rejected this model; trying Hugging Face Responses API."
                    )
                try:
                    data = self._request_huggingface_responses(
                        model_name,
                        prompt,
                        headers,
                        attachments,
                    )
                    return extract_text_from_openai_responses_response(data)
                except RuntimeError as retry_exc:
                    error_text = str(retry_exc)
                    exc = retry_exc
            self._raise_huggingface_error(model_name, exc)

    def _request_huggingface_chat(
        self,
        model_name,
        prompt,
        headers,
        attachments=None,
        use_text_content_parts=False,
    ):
        if attachments or use_text_content_parts:
            content = self._openai_content(prompt, attachments, force_parts=True)
        else:
            content = prompt
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": content}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        return request_json(
            join_url(self.base_url, "chat/completions"),
            method="POST",
            headers=headers,
            payload=payload,
            timeout=300,
        )

    def _request_huggingface_responses(self, model_name, prompt, headers, attachments=None):
        payload = {
            "model": model_name,
            "input": self._responses_input(prompt, attachments),
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
        }
        return request_json(
            join_url(self.base_url, "responses"),
            method="POST",
            headers=headers,
            payload=payload,
            timeout=300,
        )

    def _raise_huggingface_error(self, model_name, exc):
        error_text = str(exc)
        if "HTTP 401" in error_text:
            raise RuntimeError(
                "Hugging Face rejected the token. Add a valid Hugging Face token "
                "with inference permissions in Settings > API key."
            )
        if "HTTP 403" in error_text:
            raise RuntimeError(huggingface_forbidden_message(model_name))
        if (
            "model_not_supported" in error_text
            or "not supported by any provider" in error_text
        ):
            raise RuntimeError(huggingface_model_not_supported_message(model_name))
        if huggingface_is_not_chat_error(error_text):
            raise RuntimeError(huggingface_model_not_supported_message(model_name))
        raise exc

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

    def _generate_anthropic(self, model_name, prompt, attachments=None):
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        payload = {
            "model": model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {"role": "user", "content": self._anthropic_content(prompt, attachments)}
            ],
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
        rich_text=False,
    ):
        super().__init__(parent, bg=BORDER, highlightthickness=0, padx=1, pady=1)
        self.line_numbers = line_numbers
        self.rich_text = rich_text
        self._updating_numbers = False
        self._rich_after_id = None
        self._rendering_rich = False

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
        if self.rich_text:
            self._configure_rich_tags()
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
            self.schedule_rich_render()

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

    def set_content(self, value, scroll=True):
        self.text.delete("1.0", "end")
        if value:
            self.text.insert("1.0", value)
        if scroll:
            self.text.see("end")
        self.text.edit_modified(False)
        self.update_line_numbers()
        self.apply_rich_render()

    def append_content(self, value, scroll=True):
        if value:
            self.text.insert("end", value)
        if scroll:
            self.text.see("end")
        self.text.edit_modified(False)
        self.update_line_numbers()
        self.apply_rich_render()

    def clear_content(self):
        self.set_content("")

    def schedule_rich_render(self):
        if not self.rich_text:
            return
        if self._rich_after_id is not None:
            try:
                self.after_cancel(self._rich_after_id)
            except tk.TclError:
                pass
        self._rich_after_id = self.after(80, self.apply_rich_render)

    def _configure_rich_tags(self):
        self.rich_tag_names = (
            "md_markup",
            "md_heading1",
            "md_heading2",
            "md_heading3",
            "md_bold",
            "md_italic",
            "md_bold_italic",
            "md_inline_code",
            "md_code_block",
            "md_quote",
            "md_bullet",
            "md_link",
            "md_math",
            "md_strike",
        )
        try:
            self.text.tag_configure("md_markup", elide=True)
        except tk.TclError:
            self.text.tag_configure("md_markup", foreground=MUTED)
        self.text.tag_configure(
            "md_heading1",
            font=RICH_HEADING1_FONT,
            spacing1=6,
            spacing3=4,
        )
        self.text.tag_configure(
            "md_heading2",
            font=RICH_HEADING2_FONT,
            spacing1=5,
            spacing3=3,
        )
        self.text.tag_configure("md_heading3", font=RICH_HEADING3_FONT, spacing1=4)
        self.text.tag_configure("md_bold", font=RICH_BOLD_FONT)
        self.text.tag_configure("md_italic", font=RICH_ITALIC_FONT)
        self.text.tag_configure("md_bold_italic", font=RICH_BOLD_ITALIC_FONT)
        self.text.tag_configure(
            "md_inline_code",
            font=MONO_FONT,
            background="#edf2f7",
            foreground="#0f172a",
        )
        self.text.tag_configure(
            "md_code_block",
            font=MONO_FONT,
            background="#eef3f8",
            foreground=TEXT,
            lmargin1=8,
            lmargin2=8,
            rmargin=8,
            spacing1=4,
            spacing3=4,
        )
        self.text.tag_configure(
            "md_quote",
            foreground="#475569",
            background="#f1f5f9",
            lmargin1=10,
            lmargin2=10,
        )
        self.text.tag_configure("md_bullet", foreground=ACCENT, font=RICH_BOLD_FONT)
        self.text.tag_configure("md_link", foreground=ACCENT, underline=True)
        self.text.tag_configure("md_math", font=RICH_MATH_FONT, foreground="#334155")
        self.text.tag_configure("md_strike", overstrike=True)

    def apply_rich_render(self):
        if not self.rich_text or self._rendering_rich:
            return
        self._rich_after_id = None
        self._rendering_rich = True
        try:
            content = self.text.get("1.0", "end-1c")
            tag_names = getattr(self, "rich_tag_names", ())
            for tag in tag_names:
                self.text.tag_remove(tag, "1.0", "end")
            if not content:
                return
            code_ranges = self._apply_code_block_tags(content)
            self._apply_line_markdown_tags(content, code_ranges)
            self._apply_inline_markdown_tags(content, code_ranges)
        finally:
            self._rendering_rich = False

    def _index_from_offset(self, offset):
        return "1.0+" + str(max(offset, 0)) + "c"

    def _tag_range(self, tag, start, end):
        if end > start:
            self.text.tag_add(tag, self._index_from_offset(start), self._index_from_offset(end))

    def _range_overlaps(self, start, end, ranges):
        for range_start, range_end in ranges:
            if start < range_end and end > range_start:
                return True
        return False

    def _apply_code_block_tags(self, content):
        code_ranges = []
        pattern = re.compile(r"(?ms)^([ \t]*```[^\n]*)(\n)(.*?)(^[ \t]*```[ \t]*)(\n|$)")
        for match in pattern.finditer(content):
            code_ranges.append((match.start(), match.end()))
            self._tag_range("md_markup", match.start(1), match.end(1))
            self._tag_range("md_code_block", match.start(3), match.end(3))
            self._tag_range("md_markup", match.start(4), match.end(4))
        return code_ranges

    def _apply_line_markdown_tags(self, content, code_ranges):
        offset = 0
        for line in content.splitlines(True):
            line_start = offset
            line_end = offset + len(line)
            line_body = line.rstrip("\n")
            line_body_end = line_start + len(line_body)
            offset = line_end
            if self._range_overlaps(line_start, line_body_end, code_ranges):
                continue

            heading = re.match(r"^(#{1,6})([ \t]+)(.+)$", line_body)
            if heading:
                level = min(len(heading.group(1)), 3)
                text_start = line_start + heading.start(3)
                self._tag_range("md_markup", line_start, text_start)
                self._tag_range("md_heading" + str(level), text_start, line_body_end)
                continue

            quote = re.match(r"^([ \t]*>[ \t]?)(.*)$", line_body)
            if quote:
                self._tag_range("md_quote", line_start, line_body_end)
                self._tag_range("md_markup", line_start, line_start + len(quote.group(1)))
                continue

            bullet = re.match(r"^([ \t]*)([-*+])([ \t]+)", line_body)
            if bullet:
                self._tag_range(
                    "md_bullet",
                    line_start + bullet.start(2),
                    line_start + bullet.end(2),
                )
                continue

            numbered = re.match(r"^([ \t]*)(\d+[.)])([ \t]+)", line_body)
            if numbered:
                self._tag_range(
                    "md_bullet",
                    line_start + numbered.start(2),
                    line_start + numbered.end(2),
                )

    def _apply_inline_markdown_tags(self, content, code_ranges):
        def skip(start, end):
            return self._range_overlaps(start, end, code_ranges)

        def apply_pattern(pattern, tag, inner_group=2, marker_groups=(1, 3)):
            for match in re.finditer(pattern, content):
                if skip(match.start(), match.end()):
                    continue
                self._tag_range(tag, match.start(inner_group), match.end(inner_group))
                for group in marker_groups:
                    if group <= len(match.groups()):
                        self._tag_range("md_markup", match.start(group), match.end(group))

        apply_pattern(r"(?<!\\)(`+)([^`\n]+?)(\1)", "md_inline_code")
        apply_pattern(r"(?<!\\)(\*\*\*|___)([^\n]+?)(\1)", "md_bold_italic")
        apply_pattern(r"(?<!\\)(\*\*|__)([^\n]+?)(\1)", "md_bold")
        apply_pattern(r"(?<!\\)(~~)([^\n]+?)(~~)", "md_strike")
        apply_pattern(r"(?<!\\)(\$)([^$\n]+?)(\$)", "md_math")

        for match in re.finditer(r"(?<![\*\\])\*([^\n*]+?)(?<!\*)\*(?!\*)", content):
            if skip(match.start(), match.end()):
                continue
            self._tag_range("md_italic", match.start(1), match.end(1))
            self._tag_range("md_markup", match.start(), match.start() + 1)
            self._tag_range("md_markup", match.end() - 1, match.end())

        link_pattern = r"(?<!\\)(\[)([^\]\n]+)(\]\()([^) \n]+)(\))"
        for match in re.finditer(link_pattern, content):
            if skip(match.start(), match.end()):
                continue
            self._tag_range("md_link", match.start(2), match.end(2))
            self._tag_range("md_markup", match.start(1), match.end(1))
            self._tag_range("md_markup", match.start(3), match.end(3))
            self._tag_range("md_markup", match.start(4), match.end(4))
            self._tag_range("md_markup", match.start(5), match.end(5))


class HuggingFaceSearchDialog(tk.Toplevel):
    def __init__(self, app, layer):
        super().__init__(app)
        self.app = app
        self.layer = layer
        self.results = []
        self.worker = None

        self.title("Search Hugging Face models")
        self.geometry("760x520")
        self.minsize(560, 380)
        self.configure(bg=UI_BG)
        self.transient(app)

        self.search_var = tk.StringVar()
        self.task_var = tk.StringVar(value=HUGGINGFACE_DEFAULT_SEARCH_TASK)
        self.status_var = tk.StringVar(value="Ready")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.Frame(self, padding=(14, 14, 14, 8), style="App.TFrame")
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Search").grid(row=0, column=0, sticky="w")
        self.search_entry = ttk.Entry(controls, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 12))
        self.search_entry.bind("<Return>", lambda event: self.start_search())

        ttk.Label(controls, text="Type").grid(row=0, column=2, sticky="w")
        self.task_combo = ttk.Combobox(
            controls,
            textvariable=self.task_var,
            values=huggingface_task_labels(),
            state="readonly",
            width=22,
        )
        self.task_combo.grid(row=0, column=3, sticky="ew", padx=(8, 12))

        self.search_button = ttk.Button(
            controls,
            text="Search",
            command=self.start_search,
        )
        self.search_button.grid(row=0, column=4, sticky="e")

        results_frame = ttk.Frame(self, padding=(14, 0, 14, 8), style="App.TFrame")
        results_frame.grid(row=1, column=0, sticky="nsew")
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        self.result_list = tk.Listbox(
            results_frame,
            height=18,
            selectmode="extended",
            exportselection=False,
            bg=SURFACE,
            fg=TEXT,
            selectbackground=SELECTION_BG,
            selectforeground=TEXT,
            font=MONO_FONT,
            bd=1,
            relief="solid",
            highlightthickness=0,
        )
        self.result_list.grid(row=0, column=0, sticky="nsew")
        self.result_list.bind("<Double-Button-1>", lambda event: self.use_selected())

        scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.result_list.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.result_list.configure(yscrollcommand=scroll.set)

        bottom = ttk.Frame(self, padding=(14, 6, 14, 14), style="App.TFrame")
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        ttk.Label(bottom, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.use_button = ttk.Button(
            bottom,
            text="Use selected",
            command=self.use_selected,
        )
        self.use_button.grid(row=0, column=1, padx=(8, 0))
        self.add_all_button = ttk.Button(
            bottom,
            text="Add all shown",
            command=self.add_all_shown,
        )
        self.add_all_button.grid(row=0, column=2, padx=(8, 0))
        ttk.Button(bottom, text="Close", command=self.destroy).grid(
            row=0,
            column=3,
            padx=(8, 0),
        )

        self.search_entry.focus_set()
        self.after(200, self.start_search)

    def set_busy(self, is_busy):
        state = "disabled" if is_busy else "normal"
        self.search_button.configure(state=state)
        self.use_button.configure(state=state)
        self.add_all_button.configure(state=state)
        self.task_combo.configure(state="disabled" if is_busy else "readonly")

    def start_search(self):
        if self.worker and self.worker.is_alive():
            return
        query = self.search_var.get().strip()
        task_label = self.task_var.get() or HUGGINGFACE_DEFAULT_SEARCH_TASK
        api_key = self.layer.effective_api_key()
        base_url = self.layer.base_url_var.get().strip() or DEFAULT_BASE_URLS["Hugging Face"]

        self.set_busy(True)
        self.status_var.set("Searching served Hugging Face models...")
        self.result_list.delete(0, "end")
        self.result_list.insert("end", "Searching...")

        self.worker = threading.Thread(
            target=self._search_worker,
            args=(api_key, base_url, query, task_label),
            daemon=True,
        )
        self.worker.start()

    def _search_worker(self, api_key, base_url, query, task_label):
        try:
            models = list_huggingface_models(
                api_key=api_key,
                base_url=base_url,
                query=query,
                task_label=task_label,
                limit=HUGGINGFACE_SEARCH_LIMIT,
            )
        except Exception as exc:
            self.after(0, lambda: self.search_failed(str(exc)))
            return
        self.after(0, lambda: self.search_finished(models))

    def search_finished(self, models):
        self.results = models
        self.result_list.delete(0, "end")
        for model in models:
            self.result_list.insert("end", model)
        if models:
            self.result_list.selection_set(0)
            self.result_list.see(0)
            self.status_var.set(f"{len(models)} eligible models shown")
        else:
            self.status_var.set("No eligible models found")
        self.set_busy(False)

    def search_failed(self, message):
        self.results = []
        self.result_list.delete(0, "end")
        self.status_var.set("Search failed")
        self.set_busy(False)
        messagebox.showerror("Could not search Hugging Face", message, parent=self)

    def use_selected(self):
        indices = self.result_list.curselection()
        if not indices:
            messagebox.showinfo("Choose a model", "Select a model first.", parent=self)
            return
        models = [self.results[index] for index in indices if index < len(self.results)]
        self.add_models(models, close=True)

    def add_all_shown(self):
        if not self.results:
            messagebox.showinfo("No models", "Search first, then add the results.", parent=self)
            return
        self.add_models(self.results, close=False)

    def add_models(self, models, close=False):
        if not models:
            return
        self.layer.add_model_options(models, selected=models[0])
        self.layer.refresh_settings_summary()
        self.app.status_var.set("Added Hugging Face models")
        self.app.log(
            f"Added {len(models)} Hugging Face model(s) to {self.layer.display_name()}."
        )
        if close:
            self.destroy()


class LocalModelDownloadDialog(tk.Toplevel):
    def __init__(self, app, layer):
        super().__init__(app)
        self.app = app
        self.layer = layer
        self.results = []
        self.worker = None

        self.title("Search and download local models")
        self.geometry("760x520")
        self.minsize(560, 380)
        self.configure(bg=UI_BG)
        self.transient(app)

        self.search_var = tk.StringVar()
        self.source_var = tk.StringVar(value=LOCAL_MODEL_DEFAULT_SOURCE)
        self.status_var = tk.StringVar(value="Ready")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.Frame(self, padding=(14, 14, 14, 8), style="App.TFrame")
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Search or model").grid(row=0, column=0, sticky="w")
        self.search_entry = ttk.Entry(controls, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 12))
        self.search_entry.bind("<Return>", lambda event: self.start_search())

        ttk.Label(controls, text="Source").grid(row=0, column=2, sticky="w")
        self.source_combo = ttk.Combobox(
            controls,
            textvariable=self.source_var,
            values=local_model_source_labels(),
            state="readonly",
            width=20,
        )
        self.source_combo.grid(row=0, column=3, sticky="ew", padx=(8, 12))
        self.source_combo.bind("<<ComboboxSelected>>", lambda event: self.start_search())

        self.search_button = ttk.Button(
            controls,
            text="Search",
            command=self.start_search,
        )
        self.search_button.grid(row=0, column=4, sticky="e")

        results_frame = ttk.Frame(self, padding=(14, 0, 14, 8), style="App.TFrame")
        results_frame.grid(row=1, column=0, sticky="nsew")
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        self.result_list = tk.Listbox(
            results_frame,
            height=18,
            selectmode="browse",
            exportselection=False,
            bg=SURFACE,
            fg=TEXT,
            selectbackground=SELECTION_BG,
            selectforeground=TEXT,
            font=MONO_FONT,
            bd=1,
            relief="solid",
            highlightthickness=0,
        )
        self.result_list.grid(row=0, column=0, sticky="nsew")
        self.result_list.bind("<Double-Button-1>", lambda event: self.download_selected())

        scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.result_list.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.result_list.configure(yscrollcommand=scroll.set)

        bottom = ttk.Frame(self, padding=(14, 6, 14, 14), style="App.TFrame")
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        ttk.Label(bottom, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.download_button = ttk.Button(
            bottom,
            text="Download selected",
            command=self.download_selected,
        )
        self.download_button.grid(row=0, column=1, padx=(8, 0))
        self.download_typed_button = ttk.Button(
            bottom,
            text="Download typed",
            command=self.download_typed,
        )
        self.download_typed_button.grid(row=0, column=2, padx=(8, 0))
        self.use_button = ttk.Button(
            bottom,
            text="Use selected",
            command=self.use_selected,
        )
        self.use_button.grid(row=0, column=3, padx=(8, 0))
        ttk.Button(bottom, text="Close", command=self.destroy).grid(
            row=0,
            column=4,
            padx=(8, 0),
        )

        self.search_entry.focus_set()
        self.after(150, self.start_search)

    def set_busy(self, is_busy):
        state = "disabled" if is_busy else "normal"
        self.search_button.configure(state=state)
        self.download_button.configure(state=state)
        self.download_typed_button.configure(state=state)
        self.use_button.configure(state=state)
        self.source_combo.configure(state="disabled" if is_busy else "readonly")

    def start_search(self):
        if self.worker and self.worker.is_alive():
            return
        query = self.search_var.get().strip()
        source = self.source_var.get() or LOCAL_MODEL_DEFAULT_SOURCE
        self.result_list.delete(0, "end")
        self.result_list.insert("end", "Searching...")
        self.status_var.set("Searching local-download models...")

        if source in ("Hugging Face GGUF", "Hugging Face Transformers"):
            self.set_busy(True)
            api_key = self.api_key_for_source(source)
            self.worker = threading.Thread(
                target=self._search_worker,
                args=(query, source, api_key),
                daemon=True,
            )
            self.worker.start()
        else:
            self.search_finished(list_local_download_models(query=query, source=source))

    def api_key_for_source(self, source):
        if source == "Hugging Face Transformers":
            return (
                self.app.shared_keys.get("Transformers", "")
                or self.app.shared_keys.get("Hugging Face", "")
            )
        return self.app.shared_keys.get("Hugging Face", "")

    def _search_worker(self, query, source, api_key):
        try:
            models = list_local_download_models(
                query=query,
                source=source,
                api_key=api_key,
                limit=LOCAL_MODEL_SEARCH_LIMIT,
            )
        except Exception as exc:
            self.after(0, lambda: self.search_failed(str(exc)))
            return
        self.after(0, lambda: self.search_finished(models))

    def search_finished(self, models):
        self.results = models
        self.result_list.delete(0, "end")
        for model in models:
            self.result_list.insert("end", model)
        if models:
            self.result_list.selection_set(0)
            self.result_list.see(0)
            self.status_var.set(f"{len(models)} models shown")
        else:
            self.status_var.set("No models found. You can still use Download typed.")
        self.set_busy(False)

    def search_failed(self, message):
        self.results = []
        self.result_list.delete(0, "end")
        self.status_var.set("Search failed")
        self.set_busy(False)
        messagebox.showerror("Could not search models", message, parent=self)

    def selected_model(self):
        indices = self.result_list.curselection()
        if not indices:
            return ""
        index = indices[0]
        if index >= len(self.results):
            return ""
        return self.results[index]

    def typed_model(self):
        source = self.source_var.get() or LOCAL_MODEL_DEFAULT_SOURCE
        if source == "Hugging Face Transformers":
            return normalize_huggingface_repo_id(self.search_var.get())
        return normalize_ollama_model_name(self.search_var.get())

    def selected_source(self):
        return self.source_var.get() or LOCAL_MODEL_DEFAULT_SOURCE

    def is_transformers_source(self):
        return self.selected_source() == "Hugging Face Transformers"

    def download_selected(self):
        model_name = self.selected_model()
        if not model_name:
            messagebox.showinfo("Choose a model", "Select a model first.", parent=self)
            return
        if self.is_transformers_source():
            self.app.download_transformers_model_for_layer(self.layer, model_name)
        else:
            self.app.download_local_model_for_layer(self.layer, model_name)
        self.destroy()

    def download_typed(self):
        model_name = self.typed_model()
        if not model_name:
            messagebox.showinfo("Type a model", "Type a model name first.", parent=self)
            return
        if self.is_transformers_source():
            if not is_huggingface_repo_id(model_name):
                messagebox.showerror(
                    "Invalid model name",
                    "Use a Hugging Face repo ID like author/model.",
                    parent=self,
                )
                return
            self.app.download_transformers_model_for_layer(self.layer, model_name)
            self.destroy()
            return
        if not is_ollama_model_name(model_name):
            messagebox.showerror(
                "Invalid model name",
                "Use a name like qwen2.5-coder:7b or hf.co/author/model-GGUF.",
                parent=self,
            )
            return
        self.app.download_local_model_for_layer(self.layer, model_name)
        self.destroy()

    def use_selected(self):
        model_name = self.selected_model()
        if not model_name:
            messagebox.showinfo("Choose a model", "Select a model first.", parent=self)
            return
        if self.is_transformers_source():
            self.layer.use_transformers_model(model_name)
            self.app.status_var.set("Selected Transformers model")
            self.app.log("Selected local Transformers model for " + self.layer.display_name() + ": " + model_name)
        else:
            self.layer.use_ollama_model(model_name)
            self.app.status_var.set("Selected local model")
            self.app.log("Selected local Ollama model for " + self.layer.display_name() + ": " + model_name)
        self.destroy()


class LayerPanel:
    def __init__(self, app, data=None):
        self.app = app
        self.id = (data or {}).get("id") or make_id()
        self.frame = ttk.Frame(app.layers_notebook, padding=12, style="App.TFrame")
        self.model_options = list((data or {}).get("model_options", []))
        self.attachments = normalize_attachments((data or {}).get("attachments", []))

        self.name_var = tk.StringVar(value=(data or {}).get("name", "Layer"))
        raw_provider = (data or {}).get("provider", "Gemini")
        provider_value = normalize_provider_name(raw_provider)
        saved_base_url = (data or {}).get("base_url")
        if raw_provider != provider_value:
            saved_base_url = DEFAULT_BASE_URLS.get(provider_value, "")
        self.provider_var = tk.StringVar(value=provider_value)
        self.base_url_var = tk.StringVar(
            value=saved_base_url or DEFAULT_BASE_URLS.get(self.provider_var.get(), "")
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
        self.attachment_summary_var = tk.StringVar(value=attachments_summary(self.attachments))

        self._build_ui()
        self.prompt_text.insert("1.0", (data or {}).get("prompt", ""))
        self.output_cell.set_content((data or {}).get("output", ""), scroll=False)
        self.prompt_cell.update_line_numbers()
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
        tk.Label(
            self.prompt_cell.header_left,
            textvariable=self.attachment_summary_var,
            bg=SURFACE_ALT,
            fg=MUTED,
            font=SMALL_FONT,
        ).pack(side="left", padx=(12, 0))
        self.prompt_cell.add_action("Add file", self.add_attachment_files)
        self.prompt_cell.add_action("Add URL", self.add_attachment_url)
        self.prompt_cell.add_action("Clear files", self.clear_attachments)
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
            rich_text=True,
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
            label="Search Hugging Face models...",
            command=self.open_huggingface_search,
        )
        self.models_menu.add_command(
            label="Search/download local model...",
            command=self.open_local_model_download,
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
        self.settings_menu.add_command(label="Endpoint...", command=self.edit_base_url)
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
        base_url = simpledialog.askstring(
            "Endpoint",
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

    def add_model_options(self, models, selected=None):
        merged = list(self.model_options)
        merged.extend(models)
        self.set_model_options(merged, selected=selected)

    def import_models(self):
        if self.provider_var.get() == "Hugging Face":
            messagebox.showinfo(
                "Use Hugging Face search",
                "Use Models > Search Hugging Face models so LayerGen only shows served models.",
                parent=self.app,
            )
            return
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

    def open_huggingface_search(self):
        if self.provider_var.get() != "Hugging Face":
            self.provider_var.set("Hugging Face")
            self._provider_changed()
        self.refresh_settings_summary()
        HuggingFaceSearchDialog(self.app, self)

    def open_local_model_download(self):
        self.refresh_settings_summary()
        LocalModelDownloadDialog(self.app, self)

    def use_ollama_model(self, model_name):
        model_name = normalize_ollama_model_name(model_name)
        if self.provider_var.get() != "Ollama":
            self.provider_var.set("Ollama")
            self._provider_changed()
        self.add_model_options([model_name], selected=model_name)
        self.refresh_settings_summary()

    def use_transformers_model(self, model_name):
        model_name = normalize_huggingface_repo_id(model_name)
        if self.provider_var.get() != "Transformers":
            self.provider_var.set("Transformers")
            self._provider_changed()
        self.add_model_options([model_name], selected=model_name)
        self.refresh_settings_summary()

    def enter_model_name(self):
        if self.provider_var.get() == "Hugging Face":
            self.open_huggingface_search()
            return
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

    def refresh_attachment_summary(self):
        self.attachments = normalize_attachments(self.attachments)
        self.attachment_summary_var.set(attachments_summary(self.attachments))

    def add_attachment_files(self):
        paths = filedialog.askopenfilenames(
            title="Attach files to " + self.display_name(),
            filetypes=[("All files", "*.*")],
        )
        if not paths:
            return
        for path in paths:
            self.attachments.append(make_file_attachment(path))
        self.refresh_attachment_summary()
        self.app.status_var.set("Attached files")
        self.app.log(
            f"Attached {len(paths)} file{'s' if len(paths) != 1 else ''} to {self.display_name()}."
        )

    def add_attachment_url(self):
        url = simpledialog.askstring(
            "Attach URL",
            "Image or file URL:",
            parent=self.app,
        )
        if url is None:
            return
        url = url.strip()
        if not url:
            return
        if not url.lower().startswith(("http://", "https://")):
            messagebox.showerror("Invalid URL", "Use a URL starting with http:// or https://.")
            return
        self.attachments.append(make_url_attachment(url))
        self.refresh_attachment_summary()
        self.app.status_var.set("Attached URL")
        self.app.log("Attached URL to " + self.display_name() + ": " + url)

    def clear_attachments(self):
        if not self.attachments:
            return
        self.attachments = []
        self.refresh_attachment_summary()
        self.app.status_var.set("Attachments cleared")
        self.app.log("Cleared attachments for " + self.display_name() + ".")

    def clear_prompt(self):
        self.prompt_text.delete("1.0", "end")
        if hasattr(self, "prompt_cell"):
            self.prompt_cell.update_line_numbers()
        self.app.schedule_flowchart_refresh()

    def clear_output(self):
        if hasattr(self, "output_cell"):
            self.output_cell.clear_content()
        else:
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
        if hasattr(self, "output_cell"):
            self.output_cell.set_content(value)
        else:
            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", value)
            self.output_text.see("end")

    def append_output(self, value):
        existing = self.get_output()
        if existing:
            text = "\n\n" + value.strip()
        else:
            text = value.strip()
        if hasattr(self, "output_cell"):
            self.output_cell.append_content(text)
        else:
            self.output_text.insert("end", text)
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
            "attachments": normalize_attachments(self.attachments),
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
        self.global_attachments = []
        self.chat_attachments = []
        self.shared_keys = {provider: default_api_key(provider) for provider in PROVIDERS}

        self.save_keys_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")
        self.chat_layer_var = tk.StringVar(value="")
        self.chat_mode_var = tk.StringVar(value="Replace outputs")
        self.global_attachment_summary_var = tk.StringVar(value="No attachments")
        self.chat_attachment_summary_var = tk.StringVar(value="No attachments")

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
        tk.Label(
            self.input_cell.header_left,
            textvariable=self.global_attachment_summary_var,
            bg=SURFACE_ALT,
            fg=MUTED,
            font=SMALL_FONT,
        ).pack(side="left", padx=(12, 0))
        self.input_cell.add_action("Add file", self.add_global_attachment_files)
        self.input_cell.add_action("Add URL", self.add_global_attachment_url)
        self.input_cell.add_action("Clear files", self.clear_global_attachments)
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
            rich_text=True,
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
        tk.Label(
            self.chat_input_cell.header_left,
            textvariable=self.chat_attachment_summary_var,
            bg=SURFACE_ALT,
            fg=MUTED,
            font=SMALL_FONT,
        ).pack(side="left", padx=(12, 0))
        self.chat_input_cell.add_action("Add file", self.add_chat_attachment_files)
        self.chat_input_cell.add_action("Add URL", self.add_chat_attachment_url)
        self.chat_input_cell.add_action("Clear files", self.clear_chat_attachments)
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

        edges = []
        for index, layer in enumerate(layers):
            edges.extend(prompt_dependencies(layer["prompt"], index, len(layers)))

        node_boxes, input_box, full_width, full_height = self._layout_flowchart_nodes(
            len(layers),
            edges,
            canvas_width,
            canvas_height,
        )

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

            if sx < tx:
                bend = min(80, max(36, (tx - sx) / 2))
                offset = ((edge_index % 3) - 1) * 6
                points = [
                    sx,
                    sy,
                    sx + bend,
                    sy + offset,
                    tx - bend,
                    ty + offset,
                    tx,
                    ty,
                ]
                text_x = tx - bend - 8
                text_y = ty + offset - 14
            else:
                route_y = max(34, min(sy, ty) - 58 - (edge_index % 4) * 18)
                points = [sx, sy, sx + 42, route_y, tx - 42, route_y, tx, ty]
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
                max(box[3] for box in node_boxes) + 46,
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

    def _layout_flowchart_nodes(self, layer_count, edges, canvas_width, canvas_height):
        node_w = 230
        node_h = 92
        input_w = 150
        input_h = 64
        left = 38
        layer_left = 238
        top = 48
        bottom = 56
        gap_x = 168
        gap_y = 54

        incoming = {index: [] for index in range(layer_count)}
        input_targets = []
        for edge in edges:
            source = edge["source"]
            target = edge["target"]
            if 0 <= target < layer_count and source != target:
                incoming[target].append(source)
                if source == -1:
                    input_targets.append(target)

        memo = {}
        visiting = set()

        def node_level(index):
            if index in memo:
                return memo[index]
            if index in visiting:
                return 1
            visiting.add(index)
            dependency_levels = []
            for source in incoming.get(index, []):
                if source == -1:
                    dependency_levels.append(0)
                elif 0 <= source < layer_count:
                    dependency_levels.append(node_level(source))
            visiting.remove(index)
            level = max(dependency_levels) + 1 if dependency_levels else 1
            memo[index] = max(1, min(level, layer_count + 1))
            return memo[index]

        levels = {index: node_level(index) for index in range(layer_count)}
        columns = {}
        for index, level in levels.items():
            columns.setdefault(level, []).append(index)
        for level in columns:
            columns[level].sort()

        max_level = max(columns.keys(), default=1)
        max_count = max((len(nodes) for nodes in columns.values()), default=1)
        full_height = max(canvas_height, top + bottom + max_count * node_h + (max_count - 1) * gap_y)
        full_width = max(canvas_width, layer_left + max_level * (node_w + gap_x) + 48)

        center_y = full_height / 2
        node_boxes = [None] * layer_count
        desired_centers = {}

        for level in range(1, max_level + 1):
            nodes = columns.get(level, [])
            if not nodes:
                continue
            column_height = len(nodes) * node_h + (len(nodes) - 1) * gap_y
            y = max(top, center_y - column_height / 2)
            for order, index in enumerate(nodes):
                desired_centers[index] = y + order * (node_h + gap_y) + node_h / 2

        for level in range(1, max_level + 1):
            nodes = columns.get(level, [])
            if not nodes:
                continue

            ordered = []
            for index in nodes:
                source_centers = []
                for source in incoming.get(index, []):
                    if source == -1:
                        continue
                    if 0 <= source < layer_count and node_boxes[source] is not None:
                        box = node_boxes[source]
                        source_centers.append((box[1] + box[3]) / 2)
                desired = (
                    sum(source_centers) / len(source_centers)
                    if source_centers
                    else desired_centers.get(index, center_y)
                )
                ordered.append((desired, index))
            ordered.sort(key=lambda item: (item[0], item[1]))

            column_height = len(ordered) * node_h + (len(ordered) - 1) * gap_y
            min_start = top
            max_start = max(top, full_height - bottom - column_height)
            current_y = max(min_start, min(max_start, ordered[0][0] - node_h / 2))
            x = layer_left + (level - 1) * (node_w + gap_x)
            for desired, index in ordered:
                y = max(current_y, desired - node_h / 2)
                if y + node_h > full_height - bottom:
                    y = full_height - bottom - node_h
                node_boxes[index] = (x, y, x + node_w, y + node_h)
                current_y = y + node_h + gap_y

        target_centers = []
        for target in input_targets:
            if 0 <= target < len(node_boxes) and node_boxes[target] is not None:
                box = node_boxes[target]
                target_centers.append((box[1] + box[3]) / 2)
        if target_centers:
            input_center = sum(target_centers) / len(target_centers)
        else:
            input_center = center_y
        input_y = max(top, min(full_height - bottom - input_h, input_center - input_h / 2))
        input_box = (left, input_y, left + input_w, input_y + input_h)

        return node_boxes, input_box, full_width, full_height

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

    def refresh_global_attachment_summary(self):
        self.global_attachments = normalize_attachments(self.global_attachments)
        self.global_attachment_summary_var.set(attachments_summary(self.global_attachments))

    def refresh_chat_attachment_summary(self):
        self.chat_attachments = normalize_attachments(self.chat_attachments)
        self.chat_attachment_summary_var.set(attachments_summary(self.chat_attachments))

    def add_global_attachment_files(self):
        paths = filedialog.askopenfilenames(
            title="Attach project input files",
            filetypes=[("All files", "*.*")],
        )
        if not paths:
            return
        for path in paths:
            self.global_attachments.append(make_file_attachment(path))
        self.refresh_global_attachment_summary()
        self.status_var.set("Attached project files")
        self.log(f"Attached {len(paths)} project input file{'s' if len(paths) != 1 else ''}.")

    def add_global_attachment_url(self):
        url = simpledialog.askstring(
            "Attach URL",
            "Image or file URL:",
            parent=self,
        )
        if url is None:
            return
        url = url.strip()
        if not url:
            return
        if not url.lower().startswith(("http://", "https://")):
            messagebox.showerror("Invalid URL", "Use a URL starting with http:// or https://.")
            return
        self.global_attachments.append(make_url_attachment(url))
        self.refresh_global_attachment_summary()
        self.status_var.set("Attached project URL")
        self.log("Attached project input URL: " + url)

    def clear_global_attachments(self):
        if not self.global_attachments:
            return
        self.global_attachments = []
        self.refresh_global_attachment_summary()
        self.status_var.set("Project attachments cleared")
        self.log("Cleared project input attachments.")

    def add_chat_attachment_files(self):
        paths = filedialog.askopenfilenames(
            title="Attach chat message files",
            filetypes=[("All files", "*.*")],
        )
        if not paths:
            return
        for path in paths:
            self.chat_attachments.append(make_file_attachment(path))
        self.refresh_chat_attachment_summary()
        self.status_var.set("Attached chat files")
        self.log(f"Attached {len(paths)} chat file{'s' if len(paths) != 1 else ''}.")

    def add_chat_attachment_url(self):
        url = simpledialog.askstring(
            "Attach URL",
            "Image or file URL:",
            parent=self,
        )
        if url is None:
            return
        url = url.strip()
        if not url:
            return
        if not url.lower().startswith(("http://", "https://")):
            messagebox.showerror("Invalid URL", "Use a URL starting with http:// or https://.")
            return
        self.chat_attachments.append(make_url_attachment(url))
        self.refresh_chat_attachment_summary()
        self.status_var.set("Attached chat URL")
        self.log("Attached chat URL: " + url)

    def clear_chat_attachments(self):
        if not self.chat_attachments:
            return
        self.chat_attachments = []
        self.refresh_chat_attachment_summary()
        self.status_var.set("Chat attachments cleared")
        self.log("Cleared chat attachments.")

    def project_input_for_prompt(self):
        raw_input = self.input_text.get("1.0", "end-1c").strip()
        return append_attachment_context(
            raw_input,
            self.global_attachments,
            "Project input attachments",
        )

    def active_attachments_for_layer(self, layer_state, include_global=False, extra=None):
        attachments = []
        if include_global:
            attachments.extend(self.global_attachments)
        attachments.extend(layer_state.get("attachments", []))
        if extra:
            attachments.extend(extra)
        return normalize_attachments(attachments)

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
        provider = normalize_provider_name(layer_state["provider"])
        if provider not in PROVIDERS:
            raise ValueError(name + ": choose a supported provider.")
        if provider_requires_api_key(provider) and not layer_state["api_key"]:
            raise ValueError(name + ": " + api_key_required_message(provider))
        if not layer_state["base_url"]:
            raise ValueError(name + ": enter a base URL.")
        if not layer_state["model"]:
            if provider == "Hugging Face":
                raise ValueError(name + ": search Hugging Face models and choose one.")
            raise ValueError(name + ": load models and choose one.")
        if provider == "Hugging Face" and not is_huggingface_repo_id(layer_state["model"]):
            raise ValueError(name + ": choose a Hugging Face model from the search menu.")
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
        provider = normalize_provider_name(layer_state["provider"])
        if provider not in PROVIDERS:
            raise ValueError(name + ": choose a supported provider.")
        if (
            provider_requires_api_key(provider)
            and provider != "Hugging Face"
            and not layer_state["api_key"]
        ):
            raise ValueError(name + ": " + api_key_required_message(provider))
        if not layer_state["base_url"]:
            raise ValueError(name + ": enter a base URL.")

    def _load_models_worker(self, layer_id, layer_state):
        try:
            if layer_state["provider"] == "Hugging Face":
                models = list_huggingface_models(
                    api_key=layer_state["api_key"],
                    base_url=layer_state["base_url"],
                )
            else:
                client = self.client_for_layer(layer_state)
                models = client.list_models()
            if not models:
                raise RuntimeError("No compatible models were returned.")
            self.events.put(("models", layer_id, models))
            self.events.put(("done", "Ready"))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def download_local_model_for_layer(self, layer, model_name):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Still running", "Wait for the current request to finish first.")
            return
        model_name = normalize_ollama_model_name(model_name)
        if not is_ollama_model_name(model_name):
            messagebox.showerror(
                "Invalid model name",
                "Use a name like qwen2.5-coder:7b or hf.co/author/model-GGUF.",
            )
            return
        layer.use_ollama_model(model_name)
        state = layer.runtime_state()
        self.set_busy(True)
        self.status_var.set("Downloading local model...")
        self.log("Downloading local Ollama model for " + state["name"] + ": " + model_name)
        self.worker = threading.Thread(
            target=self._download_local_model_worker,
            args=(layer.id, state["base_url"], model_name),
            daemon=True,
        )
        self.worker.start()

    def _download_local_model_worker(self, layer_id, base_url, model_name):
        try:
            def report(status):
                self.events.put(("status", "Ollama download: " + status))

            pull_ollama_model(base_url, model_name, status_callback=report)
            self.events.put(("ollama_model_downloaded", layer_id, model_name))
            self.events.put(("done", "Downloaded local model"))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def download_transformers_model_for_layer(self, layer, model_name):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Still running", "Wait for the current request to finish first.")
            return
        model_name = normalize_huggingface_repo_id(model_name)
        if not is_huggingface_repo_id(model_name):
            messagebox.showerror(
                "Invalid model name",
                "Use a Hugging Face repo ID like author/model.",
            )
            return
        api_key = (
            layer.effective_api_key()
            or self.shared_keys.get("Transformers", "")
            or self.shared_keys.get("Hugging Face", "")
        )
        if api_key:
            self.shared_keys["Transformers"] = api_key
        layer.use_transformers_model(model_name)
        state = layer.runtime_state()
        if api_key:
            state["api_key"] = api_key
        self.set_busy(True)
        self.status_var.set("Downloading Transformers model...")
        self.log("Downloading local Transformers model for " + state["name"] + ": " + model_name)
        self.worker = threading.Thread(
            target=self._download_transformers_model_worker,
            args=(layer.id, model_name, state["api_key"]),
            daemon=True,
        )
        self.worker.start()

    def _download_transformers_model_worker(self, layer_id, model_name, api_key):
        try:
            def report(status):
                self.events.put(("status", "Transformers download: " + status))

            download_transformers_model(
                model_name,
                api_key=api_key,
                status_callback=report,
            )
            self.events.put(("transformers_model_downloaded", layer_id, model_name))
            self.events.put(("done", "Downloaded Transformers model"))
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

        global_input = self.project_input_for_prompt()
        global_attachments = normalize_attachments(self.global_attachments)
        self.set_busy(True)
        self.log("Running layers from " + layers[start_index]["name"] + ".")
        self.worker = threading.Thread(
            target=self._run_worker,
            args=(global_input, global_attachments, layers, start_index),
            daemon=True,
        )
        self.worker.start()

    def _run_worker(self, global_input, global_attachments, layers, start_index):
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
                prompt = append_attachment_context(
                    prompt,
                    layer.get("attachments", []),
                    layer["name"] + " attachments",
                )
                include_global = "{input}" in layer.get("prompt", "")
                attachments = []
                if include_global:
                    attachments.extend(global_attachments)
                attachments.extend(layer.get("attachments", []))
                output = self.client_for_layer(layer).generate(
                    layer["model"],
                    prompt,
                    attachments,
                )
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
        if not message and not self.chat_attachments:
            messagebox.showinfo("Empty message", "Type a chat message or attach a file first.")
            return
        if not message:
            message = "Use the attached material."
        start_index = self.chat_layer_index()
        try:
            layers = self.validate_chat(start_index)
        except Exception as exc:
            messagebox.showerror("Configuration problem", str(exc))
            return

        chat_attachments = normalize_attachments(self.chat_attachments)
        message_for_history = append_attachment_summary(
            message,
            chat_attachments,
            "Chat attachments",
        )
        self.chat_history.append(
            {
                "role": "user",
                "layer_id": layers[start_index]["id"],
                "layer_name": layers[start_index]["name"],
                "content": message_for_history,
                "attachments": chat_attachments,
                "time": now_label(),
            }
        )
        self.render_chat_history()
        self.chat_input.delete("1.0", "end")
        self.chat_attachments = []
        self.refresh_chat_attachment_summary()

        global_input = self.project_input_for_prompt()
        global_attachments = normalize_attachments(self.global_attachments)
        mode = self.chat_mode_var.get()
        history_snapshot = list(self.chat_history)
        self.set_busy(True)
        self.log("Chat fine-tuning from " + layers[start_index]["name"] + ".")
        self.worker = threading.Thread(
            target=self._chat_worker,
            args=(
                global_input,
                global_attachments,
                layers,
                start_index,
                message,
                chat_attachments,
                history_snapshot,
                mode,
            ),
            daemon=True,
        )
        self.worker.start()

    def _chat_worker(
        self,
        global_input,
        global_attachments,
        layers,
        start_index,
        message,
        chat_attachments,
        history_snapshot,
        mode,
    ):
        try:
            updated_names = []
            message_for_prompt = append_attachment_context(
                message,
                chat_attachments,
                "Chat message attachments",
            )
            for index in range(start_index, len(layers)):
                layer = layers[index]
                self.events.put(("status", "Fine-tuning " + layer["name"]))
                prompt = build_chat_prompt(
                    global_input,
                    layers,
                    index,
                    message_for_prompt,
                    history_snapshot[:-1],
                    mode,
                )
                prompt = append_attachment_context(
                    prompt,
                    layer.get("attachments", []),
                    layer["name"] + " attachments",
                )
                attachments = []
                attachments.extend(global_attachments)
                attachments.extend(layer.get("attachments", []))
                if index == start_index:
                    attachments.extend(chat_attachments)
                output = self.client_for_layer(layer).generate(
                    layer["model"],
                    prompt,
                    attachments,
                )
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
                elif event_type == "ollama_model_downloaded":
                    layer = self.layer_by_id(event[1])
                    if layer:
                        layer.use_ollama_model(event[2])
                        self.log("Downloaded local Ollama model for " + layer.display_name() + ": " + event[2])
                elif event_type == "transformers_model_downloaded":
                    layer = self.layer_by_id(event[1])
                    if layer:
                        layer.use_transformers_model(event[2])
                        self.log("Downloaded local Transformers model for " + layer.display_name() + ": " + event[2])
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
        parts = []
        for item in self.chat_history:
            role = "You" if item.get("role") == "user" else "LayerGen"
            layer_name = item.get("layer_name", "")
            stamp = item.get("time", "")
            label = role
            if layer_name:
                label += " [" + layer_name + "]"
            if stamp:
                label += " " + stamp
            parts.append(label + "\n" + item.get("content", "").rstrip() + "\n\n")
        self.chat_cell.set_content("".join(parts))
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
            "global_attachments": normalize_attachments(self.global_attachments),
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
            self.global_attachments = normalize_attachments(data.get("global_attachments", []))
            self.refresh_global_attachment_summary()
            self.chat_attachments = []
            self.refresh_chat_attachment_summary()
            self.chat_mode_var.set(data.get("chat_mode", "Replace outputs"))

            for layer_data in data.get("layers", []):
                if not layer_data.get("api_key") and layer_data.get("key_scope") == "Shared provider key":
                    layer_data["api_key"] = self.shared_keys.get(layer_data.get("provider", "Gemini"), "")
                self.add_layer(layer_data)

            self.chat_history = data.get("chat_history", [])
            for item in self.chat_history:
                if isinstance(item, dict):
                    item["attachments"] = normalize_attachments(item.get("attachments", []))
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
        self.global_attachments = []
        self.chat_attachments = []
        self.input_text.delete("1.0", "end")
        self.refresh_global_attachment_summary()
        self.refresh_chat_attachment_summary()
        self.render_chat_history()
        self.refresh_chat_layers()
        self.schedule_flowchart_refresh()
        return True

    def new_project(self):
        if (
            self.layers
            or self.chat_history
            or self.global_attachments
            or self.input_text.get("1.0", "end-1c").strip()
        ):
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
