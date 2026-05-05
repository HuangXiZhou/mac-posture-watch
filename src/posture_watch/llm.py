from __future__ import annotations

import base64
import json
import re
from typing import Any

from .config import Config
from .models import VerificationResult

VERIFY_PROMPT = """你是一个工位坐姿复核器。请判断图片中的人是否存在需要提醒的持续性坐姿问题。
重点判断：
1. 头部是否明显向前伸向屏幕；
2. 是否明显低头或颈部前屈；
3. 是否圆肩、上背塌陷；
4. 是否脸离屏幕明显过近。
注意：
- 这是提醒工具，不是医学诊断。
- 如果画面角度不足、肩颈不可见、遮挡严重，请返回 unknown。
- 不要因为轻微偏头、短暂转头、正常看屏幕就判定异常。
- 只有达到“值得打扰用户”的程度才返回 true。
- 只返回 JSON。
返回格式：
{
  "is_bad_posture": true,
  "severity": "none" | "mild" | "moderate" | "severe" | "unknown",
  "confidence": 0.0,
  "visible_evidence": ["最多3条"],
  "reason": "不超过30个中文字符"
}
通知条件：is_bad_posture=true, confidence>=0.75, severity in ["moderate","severe"]。
"""


def parse_verification_text(text: str) -> VerificationResult:
    raw = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return VerificationResult(False, "unknown", 0.0, reason="parse_failed", raw_text=raw)
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return VerificationResult(False, "unknown", 0.0, reason="parse_failed", raw_text=raw)

    evidence = data.get("visible_evidence") or []
    if not isinstance(evidence, list):
        evidence = []
    return VerificationResult(
        is_bad_posture=bool(data.get("is_bad_posture", False)),
        severity=str(data.get("severity", "unknown")),
        confidence=float(data.get("confidence", 0.0) or 0.0),
        visible_evidence=tuple(str(item)[:80] for item in evidence[:3]),
        reason=str(data.get("reason", ""))[:80],
        raw_text=raw,
    )


class OpenAICompatibleVerifier:
    def __init__(self, config: Config) -> None:
        self.config = config

    def verify(
        self,
        *,
        frame_jpeg: bytes,
        overlay_jpeg: bytes | None,
        local_score: float,
        view_type: str,
        score_reasons: tuple[str, ...],
    ) -> VerificationResult:
        if not self.config.llm_ready:
            return VerificationResult(False, "unknown", 0.0, reason="llm_not_configured")

        prompt = (
            f"{VERIFY_PROMPT}\n"
            f"本地检测信息：score={local_score:.1f}, view_type={view_type}, "
            f"reasons={','.join(score_reasons) or 'none'}。"
        )
        if self.config.llm_api_mode == "responses":
            payload = self._responses_payload(prompt, frame_jpeg, overlay_jpeg)
            text = self._post_and_extract_text("/responses", payload, "responses")
        else:
            payload = self._chat_payload(prompt, frame_jpeg, overlay_jpeg)
            text = self._post_and_extract_text("/chat/completions", payload, "chat")
        return parse_verification_text(text)

    def _chat_payload(
        self, prompt: str, frame_jpeg: bytes, overlay_jpeg: bytes | None
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.append({"type": "image_url", "image_url": {"url": _data_url(frame_jpeg), "detail": "low"}})
        if overlay_jpeg:
            content.append(
                {"type": "image_url", "image_url": {"url": _data_url(overlay_jpeg), "detail": "low"}}
            )
        payload: dict[str, Any] = {
            "model": self.config.openai_model,
            "messages": [
                {"role": "system", "content": "只输出一个 JSON 对象，不要输出 Markdown。"},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
        }
        if self.config.llm_json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _responses_payload(
        self, prompt: str, frame_jpeg: bytes, overlay_jpeg: bytes | None
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        content.append({"type": "input_image", "image_url": _data_url(frame_jpeg), "detail": "low"})
        if overlay_jpeg:
            content.append({"type": "input_image", "image_url": _data_url(overlay_jpeg), "detail": "low"})
        return {
            "model": self.config.openai_model,
            "input": [{"role": "user", "content": content}],
            "temperature": 0,
        }

    def _post_and_extract_text(self, path: str, payload: dict[str, Any], mode: str) -> str:
        import requests

        url = f"{self.config.openai_base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.config.llm_timeout_sec,
        )
        if response.status_code >= 400 and payload.pop("response_format", None) is not None:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.config.llm_timeout_sec,
            )
        response.raise_for_status()
        data = response.json()
        if mode == "responses":
            return _extract_responses_text(data)
        return data["choices"][0]["message"]["content"]


class OllamaVerifier:
    def __init__(self, config: Config) -> None:
        self.config = config

    def verify(
        self,
        *,
        frame_jpeg: bytes,
        overlay_jpeg: bytes | None,
        local_score: float,
        view_type: str,
        score_reasons: tuple[str, ...],
    ) -> VerificationResult:
        if not self.config.llm_ready:
            return VerificationResult(False, "unknown", 0.0, reason="llm_not_configured")
        payload = self._payload(
            prompt=(
                f"{VERIFY_PROMPT}\n"
                f"本地检测信息：score={local_score:.1f}, view_type={view_type}, "
                f"reasons={','.join(score_reasons) or 'none'}。"
            ),
            frame_jpeg=frame_jpeg,
            overlay_jpeg=overlay_jpeg,
        )
        text = self._post_and_extract_text(payload)
        return parse_verification_text(text)

    def _payload(
        self, prompt: str, frame_jpeg: bytes, overlay_jpeg: bytes | None
    ) -> dict[str, Any]:
        images = [_raw_base64(frame_jpeg)]
        if overlay_jpeg:
            images.append(_raw_base64(overlay_jpeg))
        payload: dict[str, Any] = {
            "model": self.config.ollama_model,
            "messages": [
                {
                    "role": "user",
                    "content": f"只输出一个 JSON 对象，不要输出 Markdown。\n{prompt}",
                    "images": images,
                }
            ],
            "stream": False,
            "keep_alive": self.config.ollama_keep_alive,
            "options": {
                "temperature": 0,
                "num_predict": 256,
            },
        }
        if self.config.llm_json_mode:
            payload["format"] = "json"
        return payload

    def _post_and_extract_text(self, payload: dict[str, Any]) -> str:
        import requests

        response = requests.post(
            f"{self.config.ollama_base_url}/api/chat",
            json=payload,
            timeout=self.config.llm_timeout_sec,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")


def create_verifier(config: Config) -> OpenAICompatibleVerifier | OllamaVerifier:
    provider = config.llm_provider.lower()
    if provider in {"ollama", "local", "gemma"}:
        return OllamaVerifier(config)
    if provider in {"openai", "openai_compatible", "compatible"}:
        return OpenAICompatibleVerifier(config)
    raise ValueError(f"Unsupported LLM_PROVIDER: {config.llm_provider}")


def _data_url(jpeg_bytes: bytes) -> str:
    encoded = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _raw_base64(jpeg_bytes: bytes) -> str:
    return base64.b64encode(jpeg_bytes).decode("ascii")


def _extract_responses_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    texts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts)
