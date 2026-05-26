"""LLM-Client-Wrapper mit integriertem Usage-Tracking."""

import json
import hashlib
import os
import re
import tempfile
import threading
import time
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
    def _process_slot_root(cls) -> str:
        configured_root = os.environ.get("LLM_PARALLEL_REQUEST_SLOT_DIR", "").strip()
        if configured_root:
            return configured_root
        return os.path.join(tempfile.gettempdir(), "mirofish-llm-slots")

    @classmethod
    def _process_slot_scope_dir(cls, base_url: Optional[str]) -> str:
        scope = (base_url or Config.LLM_BASE_URL or "default").strip().lower()
        digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:16]
        return os.path.join(cls._process_slot_root(), digest)

    @staticmethod
    def _pid_is_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return True
        return True

    @classmethod
    def _lock_file_is_stale(cls, lock_path: str) -> bool:
        try:
            with open(lock_path, "r", encoding="utf-8") as handle:
                first_line = handle.readline().strip()
        except OSError:
            return False

        if not first_line.isdigit():
            return False
        return not cls._pid_is_alive(int(first_line))

    @classmethod
    def _try_acquire_process_slot(cls, base_url: Optional[str]) -> Optional[str]:
        limit = Config.LLM_MAX_PARALLEL_REQUESTS
        if limit <= 0:
            return None

        scope_dir = cls._process_slot_scope_dir(base_url)
        os.makedirs(scope_dir, exist_ok=True)
        owner = f"{os.getpid()}\n{threading.get_ident()}\n{time.time()}\n"

        for slot_index in range(limit):
            lock_path = os.path.join(scope_dir, f"slot-{slot_index}.lock")
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if cls._lock_file_is_stale(lock_path):
                    try:
                        os.remove(lock_path)
                    except OSError:
                        pass
                continue

            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(owner)
                return lock_path
            except Exception:
                try:
                    os.remove(lock_path)
                except OSError:
                    pass
                raise

        return None

    @classmethod
    @contextmanager
    def _process_request_slot(cls, base_url: Optional[str]) -> Iterator[None]:
        limit = Config.LLM_MAX_PARALLEL_REQUESTS
        if limit <= 0:
            yield
            return

        poll_interval = max(
            0.01,
            float(os.environ.get("LLM_PARALLEL_REQUEST_POLL_INTERVAL_SECONDS", "0.05")),
        )
        lock_path = None
        while lock_path is None:
            lock_path = cls._try_acquire_process_slot(base_url)
            if lock_path is None:
                time.sleep(poll_interval)

        try:
            yield
        finally:
            if lock_path is not None:
                try:
                    os.remove(lock_path)
                except OSError:
                    pass

    @classmethod
    @contextmanager
    def request_slot(cls, base_url: Optional[str] = None) -> Iterator[None]:
        """Throttle outbound LLM requests across threads and sibling processes."""
        semaphore = cls._get_request_semaphore()
        if semaphore is not None:
            semaphore.acquire()

        try:
            with cls._process_request_slot(base_url):
                yield
        finally:
            if semaphore is not None:
                semaphore.release()

    @classmethod
    @contextmanager
    def _request_slot(cls) -> Iterator[None]:
        """Throttle outbound LLM requests inside this backend process."""
        with cls.request_slot():
            yield

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

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
        **kwargs: Any,
    ) -> Any:
        """Send a raw chat completion request through the shared LLM throttle."""
        request_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            request_kwargs["response_format"] = response_format

        request_kwargs.update(kwargs)

        with self.request_slot(self.base_url):
            response = self.client.chat.completions.create(**request_kwargs)

        self._record_usage(response)
        return response
    
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
        response = self.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

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

