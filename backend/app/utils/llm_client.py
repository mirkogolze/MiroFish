"""LLM-Client-Wrapper mit integriertem Usage-Tracking."""

import json
import re
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, Iterator, List
from openai import OpenAI

from ..config import Config


class LLMClient:
    """OpenAI-kompatibler Chat-Client mit integriertem Usage-Tracking."""

    _request_semaphore: Optional[threading.BoundedSemaphore] = None
    _request_semaphore_limit: Optional[int] = None
    _request_semaphore_lock = threading.Lock()
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        simulation_id: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        # Optional: tag every request from this client with a
        # simulation_id so per-simulation totals are accurate.
        self.simulation_id = simulation_id

        if not self.api_key:
            raise ValueError("LLM_API_KEY nicht konfiguriert")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    @classmethod
    def _get_request_semaphore(cls) -> Optional[threading.BoundedSemaphore]:
        """Return a process-wide semaphore when LLM concurrency limiting is enabled."""
        limit = Config.LLM_MAX_PARALLEL_REQUESTS
        if limit <= 0:
            return None

        with cls._request_semaphore_lock:
            if cls._request_semaphore is None or cls._request_semaphore_limit != limit:
                cls._request_semaphore = threading.BoundedSemaphore(limit)
                cls._request_semaphore_limit = limit
            return cls._request_semaphore

    @classmethod
    @contextmanager
    def _request_slot(cls) -> Iterator[None]:
        """Throttle outbound LLM requests inside this backend process."""
        semaphore = cls._get_request_semaphore()
        if semaphore is None:
            yield
            return

        semaphore.acquire()
        try:
            yield
        finally:
            semaphore.release()

    def bind_simulation(self, simulation_id: Optional[str]) -> None:
        """Attach (or clear) a simulation id for usage attribution."""
        self.simulation_id = simulation_id

    def _record_usage(self, response: Any) -> None:
        """Best-effort hook into the usage tracker. Never raises."""
        try:
            from ..services.usage_tracker import get_usage_tracker

            get_usage_tracker().record_from_openai_response(
                response,
                simulation_id=self.simulation_id,
                model=self.model,
            )
        except Exception:  # noqa: BLE001
            # Tracking is observational; never break a real call for it.
            pass
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Senden Sie eine Chatanfrage
        
        Args:
            messages: Nachrichtenliste
            temperature: Temperaturparameter
            max_tokens: Maximale Tokenanzahl
            response_format: Antwortformat (z.B. JSON-Schema)
            
        Returns:
            Modellantworttext.
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format

        with self._request_slot():
            response = self.client.chat.completions.create(**kwargs)
        # Record usage before any parsing so transient parse errors
        # do not lose cost attribution.
        self._record_usage(response)

        content = response.choices[0].message.content
        # Einige Modelle kapseln Reasoning in <think>…</think>.
        # Das wird entfernt, damit Aufrufer nur die eigentliche Antwort erhalten.
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Senden Sie eine Chatanfrage und geben Sie JSON zurück.
        
        Args:
            messages: Nachrichtenliste
            temperature: Temperaturparameter
            max_tokens: Maximale Tokenanzahl
            
        Returns:
            Verarbeitetes JSON-Objekt.
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # Bereinigung der Markdown-Codeblock-Markierungen
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"Ungültiges JSON-Format vom LLM: {cleaned_response}")

