"""
Thin client over the llama-server OpenAI-compatible API with per-request LoRA scale override.

Two endpoints:
- 8081 (4B, 3 LoRAs): suggest=0, soap_full=1, admission_fallback=2
- 8083 (9B, 1 LoRA):  admission=0
"""
import json
import time
from typing import Optional
import urllib.request
import urllib.error


# Production LoRA IDs (from emr/backend/internal/slm/client.go)
LoRA_SUGGEST_4B = 0
LoRA_SOAP_FULL_4B = 1
LoRA_ADMISSION_4B_FALLBACK = 2
LoRA_ADMISSION_9B = 0


class LlamaServerClient:
    def __init__(self, url: str, timeout: int = 120):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        try:
            req = urllib.request.Request(self.url + "/health")
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status == 200
        except Exception:
            return False

    def chat(
        self,
        messages: list,
        active_lora_id: Optional[int] = None,
        max_tokens: int = 1536,
        temperature: float = 0.3,
        repeat_penalty: float = 1.1,
    ) -> dict:
        """Send a chat completion request, optionally overriding LoRA scales.

        active_lora_id: only this LoRA gets scale=1.0; others scale=0.0.
                       If None, server's default scales are used.
        """
        payload = {
            "model": "qwen-medical",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "repeat_penalty": repeat_penalty,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }

        if active_lora_id is not None:
            adapters = self._list_adapters()
            payload["lora"] = [
                {"id": a["id"], "scale": 1.0 if a["id"] == active_lora_id else 0.0}
                for a in adapters
            ]

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.url + "/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                resp = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"HTTP {e.code} from {self.url}: {err_body}") from e
        latency = time.time() - t0

        # Strip <think>...</think> prefix if present (Qwen3 chat template artifact)
        text = resp["choices"][0]["message"]["content"]
        text = _strip_think_prefix(text)

        return {
            "text": text,
            "latency_ms": int(latency * 1000),
            "finish_reason": resp["choices"][0].get("finish_reason"),
            "usage": resp.get("usage", {}),
        }

    def _list_adapters(self) -> list:
        try:
            req = urllib.request.Request(self.url + "/lora-adapters")
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            return []


def _strip_think_prefix(s: str) -> str:
    s = s.lstrip(" \n\t")
    for p in (
        "<think>\n\n</think>\n\n",
        "<think>\n</think>\n",
        "<think></think>",
        "<think>\n\n</think>",
    ):
        if s.startswith(p):
            return s[len(p):].lstrip(" \n\t")
    if s.startswith("<think>"):
        end = s.find("</think>")
        if end >= 0:
            return s[end + len("</think>"):].lstrip(" \n\t")
    return s
