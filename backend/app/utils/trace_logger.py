"""
Verbose trace logger for MiroFish pipeline analysis.

Writes timestamped TXT files for each pipeline step, capturing full I/O
at every stage of the simulation orchestration.
"""

import os
import json
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


_LOGS_ROOT = os.path.join(os.path.dirname(__file__), '../../logs/traces')


class TraceLogger:
    """
    Per-step trace writer.

    Usage:
        trace = TraceLogger("step1a_ontology", simulation_id="abc123")
        trace.log("INPUT", "document_texts", texts)
        trace.log("LLM_REQUEST", "system_prompt", prompt)
        trace.log("LLM_RESPONSE", "ontology_json", result)
    """

    def __init__(self, step_name: str, simulation_id: Optional[str] = None):
        if simulation_id:
            folder = os.path.join(_LOGS_ROOT, simulation_id)
        else:
            folder = os.path.join(_LOGS_ROOT, "_unsorted")
        os.makedirs(folder, exist_ok=True)

        self._path = os.path.join(folder, f"{step_name}_trace.txt")
        self._lock = threading.Lock()

        with self._lock:
            with open(self._path, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"TRACE START — {step_name} — {datetime.now().isoformat()}\n")
                f.write(f"simulation_id: {simulation_id or 'N/A'}\n")
                f.write(f"{'='*80}\n\n")

    def log(self, tag: str, label: str, data: Any) -> None:
        """Append a tagged entry to the trace file."""
        ts = datetime.now().isoformat()
        with self._lock:
            with open(self._path, 'a', encoding='utf-8') as f:
                f.write(f"--- [{ts}] {tag}: {label} ---\n")
                if isinstance(data, (dict, list)):
                    f.write(json.dumps(data, ensure_ascii=False, indent=2))
                else:
                    f.write(str(data))
                f.write("\n\n")

    def section(self, title: str) -> None:
        """Write a visual section divider."""
        ts = datetime.now().isoformat()
        with self._lock:
            with open(self._path, 'a', encoding='utf-8') as f:
                f.write(f"\n{'─'*60}\n")
                f.write(f"  {title}  [{ts}]\n")
                f.write(f"{'─'*60}\n\n")


class LLMTraceHook:
    """
    Global hook that logs every LLM call made through LLMClient.

    Attach once via LLMTraceHook.install(simulation_id).
    All subsequent LLMClient.chat / chat_json calls will be traced
    until LLMTraceHook.uninstall() is called.
    """

    _instance: Optional['LLMTraceHook'] = None
    _lock = threading.Lock()

    def __init__(self, simulation_id: Optional[str] = None):
        self._trace = TraceLogger("llm_trace", simulation_id)
        self._call_count = 0

    @classmethod
    def install(cls, simulation_id: Optional[str] = None) -> 'LLMTraceHook':
        with cls._lock:
            cls._instance = cls(simulation_id)
        return cls._instance

    @classmethod
    def uninstall(cls) -> None:
        with cls._lock:
            cls._instance = None

    @classmethod
    def get(cls) -> Optional['LLMTraceHook']:
        return cls._instance

    def record(
        self,
        caller: str,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        response_text: str,
        response_format: Optional[Dict] = None,
    ) -> None:
        self._call_count += 1
        n = self._call_count
        self._trace.section(f"LLM Call #{n}  —  {caller}")
        self._trace.log("PARAM", "model", model)
        self._trace.log("PARAM", "temperature", temperature)
        self._trace.log("PARAM", "max_tokens", max_tokens)
        if response_format:
            self._trace.log("PARAM", "response_format", response_format)
        self._trace.log("INPUT", "messages", messages)
        self._trace.log("OUTPUT", "response", response_text)

    def record_direct_openai(
        self,
        caller: str,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        response_text: str,
    ) -> None:
        """Record calls made directly via OpenAI SDK (not LLMClient)."""
        self._call_count += 1
        n = self._call_count
        self._trace.section(f"Direct-OpenAI Call #{n}  —  {caller}")
        self._trace.log("PARAM", "model", model)
        self._trace.log("PARAM", "temperature", temperature)
        self._trace.log("INPUT", "messages", messages)
        self._trace.log("OUTPUT", "response", response_text)
