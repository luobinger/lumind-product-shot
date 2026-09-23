#!/usr/bin/env python3
"""使用 OpenAI 兼容图片接口生成图片。

lumind-product-shot ｜ 落落无尘（Luoluo Wuchen）出品 ｜ https://www.lumind.com.cn

配置来自环境变量或项目根目录 `.env`：
- IMG_BASE_URL: API 根地址，例如 https://api.openai.com/v1
- IMG_MODEL: 图片模型名，例如 gpt-image-1.5
- IMG_API_KEY: 使用者自己的 API key
- IMG_CONCURRENCY: 批量生成并发数，默认 3
- IMG_MAX_RETRIES: 接口遇到临时错误时的最大重试次数，默认 3
- IMG_RETRY_DELAY: 重试初始基础退避延迟（秒），默认 2.0
- IMG_TIMEOUT: 单次网络请求超时时间（秒），默认 120.0

品牌标签：lumind / 落落无尘 / Luoluo Wuchen / product-shot / PDP
"""

from __future__ import annotations

import argparse
import base64
import binascii
import concurrent.futures
import datetime
import email.utils
import http.client
import json
import os
import queue
import random
import re
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# --- Brand identity (lumind / 落落无尘) ---
SKILL_NAME = "lumind-product-shot"
BRAND_NAME = "落落无尘"
BRAND_LATIN = "Luoluo Wuchen"
BRAND_HOME = "https://www.lumind.com.cn"
BRAND_TAGS = ("lumind", "落落无尘", "Luoluo Wuchen", "product-shot", "PDP")
SCRIPT_VERSION = "1.3.0"

ENV_BASE_URL = "IMG_BASE_URL"
ENV_MODEL = "IMG_MODEL"
ENV_API_KEY = "IMG_API_KEY"
ENV_CONCURRENCY = "IMG_CONCURRENCY"
ENV_MAX_RETRIES = "IMG_MAX_RETRIES"
ENV_RETRY_DELAY = "IMG_RETRY_DELAY"
ENV_TIMEOUT = "IMG_TIMEOUT"

ENV_ALIASES = {
    ENV_BASE_URL: ("OPENAI_BASE_URL", "OPENAI_API_BASE", "BASE_URL"),
    ENV_MODEL: ("OPENAI_IMAGE_MODEL", "IMAGE_MODEL", "OPENAI_MODEL"),
    ENV_API_KEY: ("OPENAI_API_KEY", "API_KEY"),
    ENV_CONCURRENCY: ("CONCURRENCY",),
    ENV_MAX_RETRIES: ("MAX_RETRIES",),
    ENV_RETRY_DELAY: ("RETRY_DELAY",),
    ENV_TIMEOUT: ("TIMEOUT",),
}
REQUIRED_CONFIGS = (ENV_BASE_URL, ENV_MODEL, ENV_API_KEY)

ASSET_TYPE_DIRS = {
    "angle": "angle-sheet",
    "angle-sheet": "angle-sheet",
    "main": "main",
    "hero": "main",
    "detail": "detail",
    "pdp-detail": "detail",
    "extra": "extras",
    "extras": "extras",
    "custom": "custom",
}

REFERENCE_IMAGE_MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

_filename_counter = 0
_counter_lock = threading.Lock()


def get_unique_seq() -> int:
    """获取进程内全局递增序号，确保多线程并发落盘不冲突。"""
    global _filename_counter
    with _counter_lock:
        _filename_counter += 1
        return _filename_counter


class ImageApiError(Exception):
    """API 请求业务或底层网络异常。"""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None,
        transient: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_text = response_text
        self.transient = transient


@dataclass
class BatchTask:
    """批量图片生成任务单元。"""

    task_id: str
    prompt: str
    asset_type: str
    source_name: str
    size: str
    quality: str | None = None
    format: str = "png"
    n: int = 1
    image: str | None = None
    prompt_file_path: Path | None = None


@dataclass
class TaskResult:
    """单项任务执行结果记录。"""

    task: BatchTask
    status: str  # "success", "failed", "prompt_only"
    duration_seconds: float
    retries: int = 0
    prompt_path: Path | None = None
    image_paths: list[Path] = field(default_factory=list)
    error: str | None = None


def fail(message: str, exit_code: int = 1) -> None:
    print(f"错误：{message}", file=sys.stderr)
    raise SystemExit(exit_code)


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt:
        prompt = args.prompt.strip()
    elif args.prompt_file:
        try:
            prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            fail(f"无法读取 prompt 文件：{exc}")
    else:
        fail("未提供可读取的 Prompt。")

    if not prompt:
        fail("prompt 不能为空。")
    return prompt


def strip_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def find_default_env_file() -> Path | None:
    for directory in (Path.cwd(), *Path.cwd().parents):
        env_file = directory / ".env"
        if env_file.is_file():
            return env_file
    return None


def load_env_file(env_file: Path | None) -> None:
    if env_file is None:
        return
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        fail(f"无法读取 .env 文件：{exc}")

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            fail(f".env 第 {line_number} 行格式不正确，应为 KEY=value。")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            fail(f".env 第 {line_number} 行缺少变量名。")
        if key not in os.environ:
            os.environ[key] = strip_env_value(value)


def config_candidates(name: str) -> tuple[str, ...]:
    return (name, *ENV_ALIASES.get(name, ()))


def get_config(name: str) -> str | None:
    for candidate in config_candidates(name):
        value = os.environ.get(candidate, "").strip()
        if value:
            return value
    return None


def collect_config() -> tuple[dict[str, str], list[str]]:
    config: dict[str, str] = {}
    missing: list[str] = []
    for name in REQUIRED_CONFIGS:
        value = get_config(name)
        if value:
            config[name] = value
        else:
            missing.append(name)
    return config, missing


def format_missing_config(missing: list[str]) -> str:
    return "；".join(" / ".join(config_candidates(name)) for name in missing)


# --- Connection Pooling & Network Layer ---

class ConnectionPool:
    """线程安全的 HTTP/HTTPS 长连接复用池。纯标准库实现。"""

    def __init__(self, maxsize: int = 16, timeout: float = 120.0):
        self.maxsize = maxsize
        self.timeout = timeout
        self._pools: dict[tuple[str, str, int], queue.LifoQueue[http.client.HTTPConnection]] = {}
        self._lock = threading.Lock()
        self._ssl_context = ssl.create_default_context()

    def _get_queue(self, scheme: str, host: str, port: int) -> queue.LifoQueue[http.client.HTTPConnection]:
        key = (scheme.lower(), host.lower(), port)
        with self._lock:
            if key not in self._pools:
                self._pools[key] = queue.LifoQueue(maxsize=self.maxsize)
            return self._pools[key]

    def acquire(self, scheme: str, host: str, port: int) -> http.client.HTTPConnection:
        q = self._get_queue(scheme, host, port)
        while not q.empty():
            try:
                conn = q.get_nowait()
                return conn
            except queue.Empty:
                break

        proxies = urllib.request.getproxies()
        proxy_url = proxies.get(scheme.lower()) or proxies.get("all")

        if scheme.lower() == "https":
            if proxy_url:
                p = urllib.parse.urlparse(proxy_url)
                conn = http.client.HTTPSConnection(
                    p.hostname or host,
                    p.port or 443,
                    timeout=self.timeout,
                    context=self._ssl_context,
                )
                headers = {}
                if p.username and p.password:
                    auth = base64.b64encode(f"{p.username}:{p.password}".encode()).decode()
                    headers["Proxy-Authorization"] = f"Basic {auth}"
                conn.set_tunnel(host, port, headers=headers)
            else:
                conn = http.client.HTTPSConnection(
                    host,
                    port,
                    timeout=self.timeout,
                    context=self._ssl_context,
                )
        else:
            if proxy_url:
                p = urllib.parse.urlparse(proxy_url)
                conn = http.client.HTTPConnection(
                    p.hostname or host,
                    p.port or 80,
                    timeout=self.timeout,
                )
            else:
                conn = http.client.HTTPConnection(
                    host,
                    port,
                    timeout=self.timeout,
                )
        return conn

    def release(
        self,
        scheme: str,
        host: str,
        port: int,
        conn: http.client.HTTPConnection,
        close: bool = False,
    ) -> None:
        if close:
            try:
                conn.close()
            except Exception:
                pass
            return

        q = self._get_queue(scheme, host, port)
        try:
            q.put_nowait(conn)
        except queue.Full:
            try:
                conn.close()
            except Exception:
                pass

    def close_all(self) -> None:
        with self._lock:
            for q in self._pools.values():
                while not q.empty():
                    try:
                        conn = q.get_nowait()
                        conn.close()
                    except Exception:
                        pass


class HttpClient:
    """具备长连接池与指数退避重试的 HTTP/HTTPS 客户端。"""

    def __init__(
        self,
        timeout: float = 120.0,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        pool_size: int = 16,
    ):
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.retry_delay = max(0.1, retry_delay)
        self.pool = ConnectionPool(maxsize=pool_size, timeout=timeout)

    def _calc_delay(self, attempt: int, resp_headers: dict[str, str], status: int) -> float:
        if status == 429 and "retry-after" in resp_headers:
            retry_after = resp_headers["retry-after"].strip()
            if retry_after.isdigit():
                return max(0.5, min(60.0, float(retry_after)))
            try:
                dt = email.utils.parsedate_to_datetime(retry_after)
                diff = (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                if diff > 0:
                    return min(60.0, diff)
            except Exception:
                pass
        backoff = min(60.0, self.retry_delay * (2 ** attempt))
        jitter = random.uniform(0.1, 0.4)
        return backoff + jitter

    def _execute_http(
        self,
        url: str,
        method: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, dict[str, str], bytes, bool]:
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise ImageApiError(f"不支持的 URL 协议：{scheme}")

        host = parsed.hostname
        if not host:
            raise ImageApiError(f"无效的 URL 主机名：{url}")
        port = parsed.port or (443 if scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        req_headers = dict(headers)
        req_headers.setdefault("Host", host if not parsed.port else f"{host}:{parsed.port}")
        req_headers.setdefault("Connection", "keep-alive")

        conn = self.pool.acquire(scheme, host, port)
        try:
            conn.request(method, path, body=body, headers=req_headers)
            resp = conn.getresponse()
            status = resp.status
            resp_headers = {k.lower(): v for k, v in resp.getheaders()}
            data = resp.read()
            will_close = resp.will_close or resp_headers.get("connection") == "close"
            self.pool.release(scheme, host, port, conn, close=will_close)
            return status, resp_headers, data, will_close
        except (http.client.CannotSendRequest, http.client.ResponseNotReady):
            self.pool.release(scheme, host, port, conn, close=True)
            fresh_conn = self.pool.acquire(scheme, host, port)
            try:
                fresh_conn.request(method, path, body=body, headers=req_headers)
                resp = fresh_conn.getresponse()
                status = resp.status
                resp_headers = {k.lower(): v for k, v in resp.getheaders()}
                data = resp.read()
                will_close = resp.will_close or resp_headers.get("connection") == "close"
                self.pool.release(scheme, host, port, fresh_conn, close=will_close)
                return status, resp_headers, data, will_close
            except Exception as retry_exc:
                self.pool.release(scheme, host, port, fresh_conn, close=True)
                raise retry_exc
        except Exception as exc:
            self.pool.release(scheme, host, port, conn, close=True)
            raise exc

    def request_with_retry(
        self,
        url: str,
        method: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[bytes, int]:
        retries = 0
        for attempt in range(self.max_retries + 1):
            try:
                status, resp_headers, data, _ = self._execute_http(url, method, headers, body)
                if 200 <= status < 300:
                    return data, retries

                is_transient = status in (429, 500, 502, 503, 504)
                detail = data.decode("utf-8", errors="replace")
                if is_transient and attempt < self.max_retries:
                    retries += 1
                    delay = self._calc_delay(attempt, resp_headers, status)
                    status_name = http.client.responses.get(status, "Error")
                    print(
                        f"[重试 {retries}/{self.max_retries}] 接口返回 HTTP {status} ({status_name})，"
                        f"将在 {delay:.1f} 秒后重试...",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                    continue

                status_name = http.client.responses.get(status, "Error")
                raise ImageApiError(
                    f"图片接口返回 HTTP {status} ({status_name})：{detail}",
                    status_code=status,
                    response_text=detail,
                    transient=is_transient,
                )

            except (
                http.client.RemoteDisconnected,
                ConnectionResetError,
                BrokenPipeError,
                socket.timeout,
                TimeoutError,
                urllib.error.URLError,
                OSError,
            ) as exc:
                if attempt < self.max_retries:
                    retries += 1
                    delay = self._calc_delay(attempt, {}, 0)
                    err_desc = type(exc).__name__
                    if str(exc):
                        err_desc += f": {exc}"
                    print(
                        f"[重试 {retries}/{self.max_retries}] 网络连接异常 ({err_desc})，"
                        f"将在 {delay:.1f} 秒后重试...",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                    continue
                else:
                    raise ImageApiError(
                        f"网络连接异常且重试耗尽：{exc}",
                        transient=True,
                    )

        raise ImageApiError("请求失败，重试耗尽。")

    def post_json(
        self,
        url: str,
        api_key: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], int]:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "User-Agent": f"{SKILL_NAME}/{SCRIPT_VERSION}",
        }
        raw, retries = self.request_with_retry(url, "POST", headers, body)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            raise ImageApiError(f"图片接口返回的不是有效 JSON：{raw[:500].decode('utf-8', errors='replace')}")
        if not isinstance(parsed, dict):
            raise ImageApiError("图片接口返回格式不正确：顶层结果不是对象。")
        return parsed, retries

    def post_multipart(
        self,
        url: str,
        api_key: str,
        body: bytes,
        boundary: str,
    ) -> tuple[dict[str, Any], int]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Connection": "keep-alive",
            "User-Agent": f"{SKILL_NAME}/{SCRIPT_VERSION}",
        }
        raw, retries = self.request_with_retry(url, "POST", headers, body)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            raise ImageApiError(f"图片接口返回的不是有效 JSON：{raw[:500].decode('utf-8', errors='replace')}")
        if not isinstance(parsed, dict):
            raise ImageApiError("图片接口返回格式不正确：顶层结果不是对象。")
        return parsed, retries

    def download_bytes(self, url: str) -> bytes:
        current_url = url
        for _ in range(5):
            headers = {
                "Connection": "keep-alive",
                "User-Agent": f"{SKILL_NAME}/{SCRIPT_VERSION}",
            }
            status, resp_headers, data, _ = self._execute_http(current_url, "GET", headers, None)
            if status in (301, 302, 303, 307, 308) and "location" in resp_headers:
                current_url = urllib.parse.urljoin(current_url, resp_headers["location"])
                continue
            if 200 <= status < 300:
                return data
            raise ImageApiError(f"下载图片失败，HTTP {status}：{data[:200].decode('utf-8', errors='replace')}")
        raise ImageApiError(f"下载图片发生过多重定向：{url}")

    def close(self) -> None:
        self.pool.close_all()


# --- Payload & Multipart Builders ---

def build_payload(args_or_task: Any, prompt: str, model: str) -> dict[str, Any]:
    size = getattr(args_or_task, "size", "1024x1024")
    n = getattr(args_or_task, "n", 1)
    quality = getattr(args_or_task, "quality", None)
    fmt = getattr(args_or_task, "format", "png")

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": size,
    }
    if quality:
        payload["quality"] = quality
    if fmt:
        payload["output_format"] = fmt
    return payload


def multipart_boundary() -> str:
    return f"----lumind-image-boundary-{int(time.time() * 1000)}"


def multipart_field(name: str, value: str, boundary: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
        f"{value}\r\n"
    ).encode("utf-8")


def multipart_file_field(name: str, path: Path, boundary: str) -> bytes:
    try:
        image_bytes = path.read_bytes()
    except OSError as exc:
        raise ImageApiError(f"无法读取参考图片：{exc}")

    mime_type = REFERENCE_IMAGE_MIME_TYPES[path.suffix.lower().lstrip(".")]

    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    return header + image_bytes + b"\r\n"


def build_multipart_body(args_or_task: Any, prompt: str, model: str) -> tuple[bytes, str]:
    image = getattr(args_or_task, "image", None)
    if not image:
        raise ImageApiError("multipart 请求需要参考图片。")

    image_path = Path(image)
    if not image_path.is_file():
        raise ImageApiError(f"参考图片不存在：{image}")

    suffix = image_path.suffix.lower().lstrip(".")
    if suffix not in REFERENCE_IMAGE_MIME_TYPES:
        supported = "/".join(REFERENCE_IMAGE_MIME_TYPES)
        raise ImageApiError(f"不支持的参考图片格式：.{suffix}，仅支持 {supported}。")

    size = getattr(args_or_task, "size", "1024x1024")
    n = getattr(args_or_task, "n", 1)
    quality = getattr(args_or_task, "quality", None)
    fmt = getattr(args_or_task, "format", "png")

    boundary = multipart_boundary()
    parts = [
        multipart_field("model", model, boundary),
        multipart_field("prompt", prompt, boundary),
        multipart_field("n", str(n), boundary),
        multipart_field("size", size, boundary),
    ]
    if quality:
        parts.append(multipart_field("quality", quality, boundary))
    if fmt:
        parts.append(multipart_field("output_format", fmt, boundary))
    parts.append(multipart_file_field("image", image_path, boundary))
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), boundary


# --- Storage & Filename Helpers ---

def safe_filename_stem(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isascii() and (char.isalnum() or char in {"-", "_"}):
            chars.append(char)
        elif char in {" ", ".", "/", "\\"}:
            chars.append("-")
    stem = "".join(chars).strip("-_")
    return stem or "prompt"


def filename_for(index: int, suffix: str, stem: str | None = None) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    seq = get_unique_seq()
    clean_suffix = suffix.lstrip(".")
    if stem:
        safe_stem = safe_filename_stem(stem)
        return f"{safe_stem}-{timestamp}-{seq:03d}-{index + 1:02d}.{clean_suffix}"
    return f"image-{timestamp}-{seq:03d}-{index + 1:02d}.{clean_suffix}"


def suffix_from_url(url: str, fallback: str) -> str:
    path = urllib.parse.urlparse(url).path
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in {"png", "jpg", "jpeg", "webp"}:
        return "jpg" if suffix == "jpeg" else suffix
    return fallback


def save_prompt(
    prompt: str,
    job_dir: Path | str | None,
    asset_type: str,
    source_stem: str,
) -> Path | None:
    if not job_dir:
        return None

    prompt_dir = Path(job_dir) / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    seq = get_unique_seq()
    stem = safe_filename_stem(source_stem)
    dir_name = ASSET_TYPE_DIRS.get(asset_type, "custom")
    output_path = prompt_dir / f"{dir_name}-{stem}-{timestamp}-{seq:03d}.txt"
    try:
        output_path.write_text(f"{prompt}\n", encoding="utf-8")
    except OSError as exc:
        raise ImageApiError(f"无法写入 Prompt 文件：{exc}")
    return output_path


def resolve_output_dir(args: argparse.Namespace) -> Path:
    if args.job_dir:
        return Path(args.job_dir) / ASSET_TYPE_DIRS.get(args.asset_type, "custom")
    return Path(args.output_dir)


def print_prompt_only(prompt: str, prompt_path: Path | None, missing: list[str]) -> None:
    if missing:
        print("图片 API 配置未完整，已按 auto 模式只输出 Prompt。")
        print(f"缺少配置：{format_missing_config(missing)}")
        print("补齐 IMG_BASE_URL、IMG_MODEL、IMG_API_KEY 后，同一命令会默认直接生成图片。")
    else:
        print("已按 prompt 模式只输出 Prompt。")
    if prompt_path:
        print(f"Prompt 已保存：{prompt_path}")
    print("Prompt：")
    print(prompt)


def image_endpoint(base_url: str, args_or_task: Any) -> str:
    image = getattr(args_or_task, "image", None)
    if image:
        return f"{base_url}/images/edits"
    return f"{base_url}/images/generations"


def save_b64_image(
    item: dict[str, Any],
    output_dir: Path,
    index: int,
    fmt: str,
    stem: str | None = None,
) -> Path:
    encoded = item.get("b64_json")
    if not isinstance(encoded, str) or not encoded:
        raise ImageApiError("图片结果缺少 b64_json。")

    try:
        image_bytes = base64.b64decode(encoded)
    except (binascii.Error, ValueError) as exc:
        raise ImageApiError(f"无法解码 b64_json 图片：{exc}")

    output_path = output_dir / filename_for(index, fmt, stem=stem)
    try:
        output_path.write_bytes(image_bytes)
    except OSError as exc:
        raise ImageApiError(f"无法写入图片文件：{exc}")
    return output_path


def save_url_image(
    item: dict[str, Any],
    output_dir: Path,
    index: int,
    fmt: str,
    client: HttpClient | None = None,
    stem: str | None = None,
) -> Path:
    image_url = item.get("url")
    if not isinstance(image_url, str) or not image_url:
        raise ImageApiError("图片结果缺少 url。")

    suffix = suffix_from_url(image_url, fmt)
    output_path = output_dir / filename_for(index, suffix, stem=stem)

    if client:
        try:
            image_bytes = client.download_bytes(image_url)
        except Exception as exc:
            raise ImageApiError(f"无法下载图片 URL ({image_url})：{exc}")
    else:
        try:
            with urllib.request.urlopen(image_url, timeout=120) as response:
                image_bytes = response.read()
        except urllib.error.URLError as exc:
            raise ImageApiError(f"无法下载图片 URL：{exc.reason}")
        except TimeoutError:
            raise ImageApiError("下载图片超时。")

    try:
        output_path.write_bytes(image_bytes)
    except OSError as exc:
        raise ImageApiError(f"无法写入图片文件：{exc}")

    return output_path


def save_images(
    result: dict[str, Any],
    output_dir: Path,
    fmt: str,
    client: HttpClient | None = None,
    stem: str | None = None,
) -> list[Path]:
    data = result.get("data")
    if not isinstance(data, list) or not data:
        raise ImageApiError("图片接口返回中没有 data 图片数组。")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ImageApiError("图片接口返回格式不正确：data 中包含非对象项目。")
        if item.get("b64_json"):
            paths.append(save_b64_image(item, output_dir, index, fmt, stem=stem))
        elif item.get("url"):
            paths.append(save_url_image(item, output_dir, index, fmt, client=client, stem=stem))
        else:
            raise ImageApiError("图片结果既没有 b64_json，也没有 url。")
    return paths


# --- Batch Task Discovery ---

def natural_sort_key(p: Path) -> list[Any]:
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", str(p))]


def infer_asset_type_from_path(p: Path, default_type: str) -> str:
    parent_name = p.parent.name.lower()
    if parent_name in ASSET_TYPE_DIRS:
        return ASSET_TYPE_DIRS[parent_name]

    stem_lower = p.stem.lower()
    if "angle" in stem_lower:
        return "angle-sheet"
    if "main" in stem_lower or "hero" in stem_lower:
        return "main"
    if "detail" in stem_lower or "pdp" in stem_lower:
        return "detail"
    if "extra" in stem_lower:
        return "extras"

    return default_type


def infer_size_for_task(asset_type: str, explicit_size: str | None) -> str:
    if explicit_size:
        return explicit_size
    if asset_type in ("detail", "pdp-detail"):
        return "1024x1536"
    return "1024x1024"


def collect_batch_tasks_from_dir(dir_path: Path, args: argparse.Namespace) -> list[BatchTask]:
    if not dir_path.is_dir():
        fail(f"指定批量目录不存在或不是目录：{dir_path}")

    files: list[Path] = []
    for ext in ("*.txt", "*.prompt", "*.md"):
        for f in dir_path.glob(ext):
            if f.is_file() and not f.name.startswith((".", "README", "LICENSE", "SUMMARY")):
                files.append(f)

    for sub in dir_path.iterdir():
        if sub.is_dir() and not sub.name.startswith((".", "__")):
            for ext in ("*.txt", "*.prompt", "*.md"):
                for f in sub.glob(ext):
                    if f.is_file() and not f.name.startswith((".", "README", "LICENSE", "SUMMARY")):
                        files.append(f)

    files = sorted(set(files), key=natural_sort_key)
    if not files:
        fail(f"在目录 {dir_path} 中未找到有效的 Prompt 文本文件（.txt / .prompt / .md）。")

    tasks: list[BatchTask] = []
    explicit_size = args.size if args._size_explicit else None

    for idx, p in enumerate(files):
        try:
            content = p.read_text(encoding="utf-8").strip()
        except OSError as exc:
            print(f"[警告] 无法读取文件 {p}：{exc}，已跳过。", file=sys.stderr)
            continue

        if not content:
            continue

        asset_type = infer_asset_type_from_path(p, args.asset_type)
        size = infer_size_for_task(asset_type, explicit_size)

        tasks.append(
            BatchTask(
                task_id=f"{idx + 1:02d}-{p.stem}",
                prompt=content,
                asset_type=asset_type,
                source_name=p.stem,
                size=size,
                quality=args.quality,
                format=args.format,
                n=args.n,
                image=args.image,
                prompt_file_path=p,
            )
        )

    if not tasks:
        fail(f"目录 {dir_path} 中的 Prompt 文件均为有效空白，未能提取出可用任务。")
    return tasks


def collect_batch_tasks_from_file(file_path: Path, args: argparse.Namespace) -> list[BatchTask]:
    if not file_path.is_file():
        fail(f"指定批量清单文件不存在：{file_path}")

    try:
        content = file_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        fail(f"无法读取清单文件 {file_path}：{exc}")

    tasks: list[BatchTask] = []
    explicit_size = args.size if args._size_explicit else None

    # 1. 尝试解析为 JSON 数组或包含 tasks 的 JSON
    try:
        parsed_json = json.loads(content)
        items = parsed_json if isinstance(parsed_json, list) else parsed_json.get("tasks", [])
        if isinstance(items, list):
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                prompt = item.get("prompt", "").strip()
                prompt_file = item.get("prompt_file")
                source_name = item.get("name") or item.get("id") or f"task-{idx + 1:02d}"

                if not prompt and prompt_file:
                    pf = Path(prompt_file)
                    if not pf.is_absolute():
                        pf = file_path.parent / pf
                    if pf.is_file():
                        prompt = pf.read_text(encoding="utf-8").strip()
                        source_name = pf.stem

                if not prompt:
                    continue

                asset_type = item.get("asset_type") or args.asset_type
                size = item.get("size") or infer_size_for_task(asset_type, explicit_size)

                tasks.append(
                    BatchTask(
                        task_id=f"{idx + 1:02d}-{safe_filename_stem(source_name)}",
                        prompt=prompt,
                        asset_type=asset_type,
                        source_name=source_name,
                        size=size,
                        quality=item.get("quality") or args.quality,
                        format=item.get("format") or args.format,
                        n=int(item.get("n", args.n)),
                        image=item.get("image") or args.image,
                        prompt_file_path=Path(prompt_file) if prompt_file else None,
                    )
                )
    except json.JSONDecodeError:
        pass

    # 2. 若未解析出任务，尝试逐行（JSONL 或纯文件路径列表）
    if not tasks:
        for idx, line in enumerate(content.splitlines()):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # 尝试单行 JSON
            if line.startswith("{") and line.endswith("}"):
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        prompt = obj.get("prompt", "").strip()
                        source_name = obj.get("name") or f"task-{idx + 1:02d}"
                        asset_type = obj.get("asset_type") or args.asset_type
                        size = obj.get("size") or infer_size_for_task(asset_type, explicit_size)
                        if prompt:
                            tasks.append(
                                BatchTask(
                                    task_id=f"{len(tasks) + 1:02d}-{safe_filename_stem(source_name)}",
                                    prompt=prompt,
                                    asset_type=asset_type,
                                    source_name=source_name,
                                    size=size,
                                    quality=obj.get("quality") or args.quality,
                                    format=obj.get("format") or args.format,
                                    n=int(obj.get("n", args.n)),
                                    image=obj.get("image") or args.image,
                                )
                            )
                            continue
                except json.JSONDecodeError:
                    pass

            # 纯文件路径处理
            p = Path(line)
            if not p.is_absolute():
                p = file_path.parent / p
            if p.is_file():
                try:
                    file_prompt = p.read_text(encoding="utf-8").strip()
                    if file_prompt:
                        asset_type = infer_asset_type_from_path(p, args.asset_type)
                        size = infer_size_for_task(asset_type, explicit_size)
                        tasks.append(
                            BatchTask(
                                task_id=f"{len(tasks) + 1:02d}-{p.stem}",
                                prompt=file_prompt,
                                asset_type=asset_type,
                                source_name=p.stem,
                                size=size,
                                quality=args.quality,
                                format=args.format,
                                n=args.n,
                                image=args.image,
                                prompt_file_path=p,
                            )
                        )
                except OSError as exc:
                    print(f"[警告] 无法读取清单中引用的文件 {p}：{exc}", file=sys.stderr)

    if not tasks:
        fail(f"在清单文件 {file_path} 中未能解析出任何可用任务。")
    return tasks


# --- Batch Execution Pipeline ---

def execute_batch(
    tasks: list[BatchTask],
    args: argparse.Namespace,
    config: dict[str, str],
    missing: list[str],
) -> int:
    concurrency = args.concurrency if args.concurrency is not None else int(get_config(ENV_CONCURRENCY) or 3)
    concurrency = max(1, min(concurrency, 32))
    max_retries = args.max_retries if args.max_retries is not None else int(get_config(ENV_MAX_RETRIES) or 3)
    retry_delay = args.retry_delay if args.retry_delay is not None else float(get_config(ENV_RETRY_DELAY) or 2.0)
    timeout = args.timeout if args.timeout is not None else float(get_config(ENV_TIMEOUT) or 120.0)

    if args.job_dir:
        job_dir = Path(args.job_dir)
    else:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        job_dir = Path(f"generated-images/batch-{timestamp}")
    job_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "prompt" or missing:
        if missing:
            print("图片 API 配置未完整，已按 auto 模式批量输出并保存 Prompt。")
            print(f"缺少配置：{format_missing_config(missing)}")
            print("补齐 IMG_BASE_URL、IMG_MODEL、IMG_API_KEY 后，同一命令会默认直接并发生成图片。")
        else:
            print("已按 prompt 模式批量保存 Prompt。")

        saved_prompts: list[Path] = []
        for task in tasks:
            p_path = save_prompt(task.prompt, job_dir, task.asset_type, task.source_name)
            if p_path:
                saved_prompts.append(p_path)

        print(f"共提取并保存 {len(saved_prompts)} 个 Prompt 文件到：{job_dir / 'prompts'}")
        for p in saved_prompts:
            print(f"  - {p}")
        return 0

    base_url = config[ENV_BASE_URL].rstrip("/")
    model = config[ENV_MODEL]
    api_key = config[ENV_API_KEY]

    client = HttpClient(
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
        pool_size=concurrency * 2,
    )

    total = len(tasks)
    print("=" * 60)
    print(f"启动批量任务：共 {total} 项 ｜ 并发度 {concurrency} ｜ 重试上限 {max_retries} ｜ 目录：{job_dir}")
    print("=" * 60)

    start_time = time.time()
    results: list[TaskResult] = []
    completed_count = 0
    progress_lock = threading.Lock()

    def run_task(idx: int, task: BatchTask) -> TaskResult:
        nonlocal completed_count
        task_start = time.time()
        prompt_path = save_prompt(task.prompt, job_dir, task.asset_type, task.source_name)
        asset_subdir = ASSET_TYPE_DIRS.get(task.asset_type, "custom")
        out_dir = job_dir / asset_subdir

        endpoint = image_endpoint(base_url, task)
        try:
            if task.image:
                body, boundary = build_multipart_body(task, task.prompt, model)
                resp_json, retries = client.post_multipart(endpoint, api_key, body, boundary)
            else:
                payload = build_payload(task, task.prompt, model)
                resp_json, retries = client.post_json(endpoint, api_key, payload)

            paths = save_images(
                resp_json,
                out_dir,
                task.format,
                client=client,
                stem=task.source_name,
            )
            duration = time.time() - task_start

            with progress_lock:
                completed_count += 1
                cur = completed_count
                retries_str = f", 重试 {retries} 次" if retries > 0 else ""
                print(f"[{cur:02d}/{total:02d}] [完成] {task.task_id} ({task.asset_type}, 耗时 {duration:.1f}s{retries_str})")

            return TaskResult(
                task=task,
                status="success",
                duration_seconds=round(duration, 2),
                retries=retries,
                prompt_path=prompt_path,
                image_paths=paths,
            )
        except Exception as exc:
            duration = time.time() - task_start
            err_msg = str(exc)
            with progress_lock:
                completed_count += 1
                cur = completed_count
                print(f"[{cur:02d}/{total:02d}] [失败] {task.task_id} ({task.asset_type}, 耗时 {duration:.1f}s) - 原因：{err_msg}")

            return TaskResult(
                task=task,
                status="failed",
                duration_seconds=round(duration, 2),
                retries=max_retries,
                prompt_path=prompt_path,
                error=err_msg,
            )

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_task = {
                executor.submit(run_task, i, task): task
                for i, task in enumerate(tasks)
            }
            for future in concurrent.futures.as_completed(future_to_task):
                res = future.result()
                results.append(res)
    finally:
        client.close()

    total_duration = time.time() - start_time
    succeeded = [r for r in results if r.status == "success"]
    failed = [r for r in results if r.status == "failed"]

    # 写入结构化汇总 JSON
    summary_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "job_dir": str(job_dir),
        "total": total,
        "succeeded": len(succeeded),
        "failed": len(failed),
        "concurrency": concurrency,
        "total_duration_seconds": round(total_duration, 2),
        "tasks": [
            {
                "id": r.task.task_id,
                "asset_type": r.task.asset_type,
                "size": r.task.size,
                "status": r.status,
                "duration_seconds": r.duration_seconds,
                "retries": r.retries,
                "prompt_path": str(r.prompt_path) if r.prompt_path else None,
                "images": [str(p) for p in r.image_paths],
                "error": r.error,
            }
            for r in results
        ],
    }
    summary_path = job_dir / "batch-summary.json"
    try:
        summary_path.write_text(json.dumps(summary_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"无法写入任务汇总文件：{exc}", file=sys.stderr)

    print("=" * 60)
    print(f"批量执行结算：总计 {total} ｜ 成功 {len(succeeded)} ｜ 失败 {len(failed)} ｜ 耗时 {total_duration:.1f}s")
    print(f"结构化清单报告：{summary_path}")
    print("=" * 60)

    if succeeded:
        print("成功产物列表：")
        for r in succeeded:
            for p in r.image_paths:
                print(f"  - [{r.task.asset_type}] {r.task.task_id} -> {p}")

    if failed:
        print("\n失败任务列表与重试建议：", file=sys.stderr)
        for r in failed:
            print(f"  - [{r.task.asset_type}] {r.task.task_id}: {r.error}", file=sys.stderr)
            if r.prompt_path:
                print(
                    f"    单项重试命令：python3 scripts/generate_image.py --prompt-file {r.prompt_path} "
                    f"--job-dir {job_dir} --asset-type {r.task.asset_type} --size {r.task.size}",
                    file=sys.stderr,
                )
        return 2

    return 0


# --- Brand & CLI Parsing ---

def print_brand_lockup() -> None:
    print(f"{SKILL_NAME} v{SCRIPT_VERSION}")
    print(f"品牌：{BRAND_NAME}（{BRAND_LATIN}）")
    print(f"官网：{BRAND_HOME}")
    print(f"标签：{' / '.join(BRAND_TAGS)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=SKILL_NAME,
        description=(
            "使用 IMG_* 环境变量调用 OpenAI 兼容图片接口生成图片。"
            f"{BRAND_NAME}（{BRAND_LATIN}）出品。"
        ),
        epilog=f"{SKILL_NAME} ｜ {BRAND_NAME}（{BRAND_LATIN}）出品 ｜ {BRAND_HOME}",
    )
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", help="直接传入图片生成 Prompt。")
    prompt_group.add_argument("--prompt-file", help="从文本文件读取图片生成 Prompt。")
    prompt_group.add_argument(
        "--batch-dir",
        "--prompts-dir",
        dest="batch_dir",
        help="包含多个 Prompt 文本文件的目录，按文件名顺序批量并发执行。",
    )
    prompt_group.add_argument(
        "--batch-file",
        "--manifest",
        dest="batch_file",
        help="批量任务清单文件（支持 JSON 数组、JSONL 或按行列表）。",
    )

    parser.add_argument(
        "--about",
        action="store_true",
        help="输出技能名称、版本与品牌信息后退出。",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "prompt", "image"),
        default="auto",
        help="输出模式：auto 配置完整则生图、配置缺失则输出 Prompt；prompt 只输出 Prompt；image 强制生图。",
    )
    parser.add_argument(
        "--job-dir",
        help="单次任务根目录，例如 generated-images/product-pack-20260509-010946；传入后按 asset-type 自动归类。",
    )
    parser.add_argument(
        "--asset-type",
        choices=tuple(ASSET_TYPE_DIRS),
        default="custom",
        help="任务资产类型：angle-sheet 临时角度图，main 主图，detail 详情页，extras 额外变体，custom 其他。",
    )
    parser.add_argument(
        "--output-dir",
        default="generated-images",
        help="旧版图片输出目录，默认 generated-images；传入 --job-dir 后由 job-dir/asset-type 接管。",
    )
    parser.add_argument(
        "--env-file",
        help="指定 .env 配置文件；不指定时从当前目录向上查找 .env。",
    )
    parser.add_argument("--size", default="1024x1024", help="图片尺寸，默认 1024x1024。")
    parser.add_argument("--quality", help="图片质量参数，例如 low、medium、high。")
    parser.add_argument(
        "--format",
        choices=("png", "jpeg", "webp"),
        default="png",
        help="期望图片格式，默认 png。",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=1,
        help="生成图片数量，默认 1。",
    )
    parser.add_argument(
        "--image",
        help="参考产品图片路径；传入后改用图片编辑接口生成更一致的商品图。",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=None,
        help="批量生成时的并发数，默认 3（范围 1-32）。单图模式下忽略。",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="请求临时失败时的最大重试次数，默认 3 次。设置为 0 禁用重试。",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=None,
        help="重试初始基础退避延迟（秒），默认 2.0 秒。",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="单次网络请求超时时间（秒），默认 120.0 秒。",
    )

    args = parser.parse_args()
    if args.about:
        return args

    has_prompt = bool(args.prompt or args.prompt_file or args.batch_dir or args.batch_file)
    if not has_prompt:
        parser.error("必须提供 --prompt、--prompt-file、--batch-dir 或 --batch-file；仅查看品牌信息请使用 --about。")

    if args.n < 1:
        fail("--n 必须大于等于 1。")
    if args.concurrency is not None and (args.concurrency < 1 or args.concurrency > 32):
        fail("--concurrency 必须在 1 到 32 之间。")
    if args.max_retries is not None and args.max_retries < 0:
        fail("--max-retries 必须大于等于 0。")
    if args.retry_delay is not None and args.retry_delay < 0:
        fail("--retry-delay 必须大于等于 0。")
    if args.timeout is not None and args.timeout <= 0:
        fail("--timeout 必须大于 0。")

    # 标记 --size 是否由命令行显式提供
    args._size_explicit = any(arg == "--size" or arg.startswith("--size=") for arg in sys.argv)
    return args


def main() -> None:
    args = parse_args()
    if args.about:
        print_brand_lockup()
        return

    env_file = Path(args.env_file) if args.env_file else find_default_env_file()
    load_env_file(env_file)

    config, missing = collect_config()
    if missing and args.mode == "image":
        fail(
            "image 模式需要完整图片 API 配置。缺少配置："
            f"{format_missing_config(missing)}。"
        )

    # 批量模式分流
    if args.batch_dir:
        tasks = collect_batch_tasks_from_dir(Path(args.batch_dir), args)
        code = execute_batch(tasks, args, config, missing)
        sys.exit(code)

    if args.batch_file:
        tasks = collect_batch_tasks_from_file(Path(args.batch_file), args)
        code = execute_batch(tasks, args, config, missing)
        sys.exit(code)

    # 单图模式
    prompt = read_prompt(args)
    source_stem = Path(args.prompt_file).stem if args.prompt_file else "prompt"
    prompt_path = save_prompt(prompt, args.job_dir, args.asset_type, source_stem)

    if args.mode == "prompt" or missing:
        print_prompt_only(prompt, prompt_path, missing if args.mode == "auto" else [])
        return

    base_url = config[ENV_BASE_URL].rstrip("/")
    model = config[ENV_MODEL]
    api_key = config[ENV_API_KEY]

    max_retries = args.max_retries if args.max_retries is not None else int(get_config(ENV_MAX_RETRIES) or 3)
    retry_delay = args.retry_delay if args.retry_delay is not None else float(get_config(ENV_RETRY_DELAY) or 2.0)
    timeout = args.timeout if args.timeout is not None else float(get_config(ENV_TIMEOUT) or 120.0)

    client = HttpClient(
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
        pool_size=2,
    )

    try:
        endpoint = image_endpoint(base_url, args)
        if args.image:
            body, boundary = build_multipart_body(args, prompt, model)
            result, retries = client.post_multipart(endpoint, api_key, body, boundary)
        else:
            payload = build_payload(args, prompt, model)
            result, retries = client.post_json(endpoint, api_key, payload)

        paths = save_images(
            result,
            resolve_output_dir(args),
            args.format,
            client=client,
            stem=source_stem,
        )
    except ImageApiError as exc:
        fail(str(exc))
    finally:
        client.close()

    print("生成完成：")
    if prompt_path:
        print(f"Prompt 已保存：{prompt_path}")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
