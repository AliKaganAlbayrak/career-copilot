"""Dil modeli (LLM) istemcisi.

Uygulamanın geri kalanı yalnızca LLMClient arayüzünü tanır; arkasında
hangi sağlayıcının durduğunu bilmez. Bugün yerel Ollama kullanıyoruz,
yarın bulut API'sine geçmek için yeni bir sınıf yazmak yeterli olur.
Testlerde de aynı arayüzü uygulayan sahte bir istemci kullanılır.
"""

from __future__ import annotations

import os
from typing import Protocol

import httpx


class LLMError(Exception):
    """Modele ulaşılamadığında ya da yanıt okunamadığında fırlatılır."""


class LLMClient(Protocol):
    """Her sağlayıcının uygulaması gereken tek yöntem."""

    def generate(self, prompt: str, *, system: str, json_mode: bool = False) -> str:
        """Modelden metin üretir. json_mode açıksa yanıt geçerli JSON olmalıdır."""
        ...


class OllamaClient:
    """Yerelde çalışan Ollama sunucusuyla konuşur (veri bilgisayardan çıkmaz)."""

    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, *, system: str, json_mode: bool = False) -> str:
        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,  # yanıtı parça parça değil tek seferde al
        }
        if json_mode:
            payload["format"] = "json"

        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return str(response.json()["response"])
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LLMError(f"Ollama isteği başarısız oldu: {exc}") from exc


def get_llm_client() -> LLMClient:
    """FastAPI bağımlılığı: ayarlardan bir istemci üretir.

    Testler bunu dependency_overrides ile sahte istemciyle değiştirir.
    """
    return OllamaClient(
        base_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        model=os.getenv("OLLAMA_MODEL", "llama3"),
    )
