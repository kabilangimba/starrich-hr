"""Ollama adapter for locally hosted models.

Uses plain HTTP (`requests` ships with Frappe) rather than adding an SDK, and
needs no API key - `base_url` points at the local daemon.
"""

from __future__ import annotations

from typing import Any

import requests
from frappe import _

from ai_hr.ai.base import AIConfig, AIProvider, AIProviderError, AIResult

DEFAULT_BASE_URL = "http://127.0.0.1:11434"


class OllamaProvider(AIProvider):
	name = "Ollama"
	default_model = "llama3.1"

	def __init__(self, config: AIConfig) -> None:
		super().__init__(config)
		self.base_url = (config.base_url or DEFAULT_BASE_URL).rstrip("/")

	def _send(self, system: str, prompt: str, schema: dict[str, Any] | None = None) -> AIResult:
		model = self.config.model or self.default_model
		payload: dict[str, Any] = {
			"model": model,
			"stream": False,
			"messages": [
				{"role": "system", "content": system},
				{"role": "user", "content": prompt},
			],
			"options": {"num_predict": self.config.max_tokens},
		}
		if schema is not None:
			# Recent Ollama builds constrain decoding to a JSON Schema; older ones
			# accept only "json". Either way the prompt also states the contract.
			payload["format"] = schema

		try:
			response = requests.post(
				f"{self.base_url}/api/chat", json=payload, timeout=self.config.timeout
			)
		except requests.exceptions.ConnectionError:
			raise AIProviderError(
				_("Could not reach Ollama at {0}. Is the daemon running?").format(self.base_url)
			)
		except requests.exceptions.Timeout:
			raise AIProviderError(
				_(
					"Ollama did not respond within {0}s. Local models can be slow on first "
					"load - raise Request Timeout in AI HR Settings, or use a smaller model."
				).format(self.config.timeout)
			)

		# Ollama reports model problems as JSON, sometimes with a 4xx and sometimes
		# with a 200. Read the body first so the real reason is not lost behind a
		# bare status code.
		try:
			data = response.json()
		except ValueError:
			response.raise_for_status()
			raise AIProviderError(_("Ollama returned an unreadable response."))

		if error := data.get("error"):
			raise AIProviderError(self._explain(str(error), model))

		if not response.ok:
			raise AIProviderError(
				_("Ollama returned HTTP {0}: {1}").format(response.status_code, str(data)[:200])
			)

		content = (data.get("message") or {}).get("content", "")
		if not content.strip():
			raise AIProviderError(
				_("Ollama returned an empty response from model {0}.").format(model)
			)

		return AIResult(
			text=content,
			model=data.get("model", model),
			provider=self.name,
			input_tokens=data.get("prompt_eval_count", 0) or 0,
			output_tokens=data.get("eval_count", 0) or 0,
		)

	def _explain(self, error: str, model: str) -> str:
		"""Turn Ollama's raw error into something a recruiter can act on."""
		lowered = error.lower()

		if "more system memory" in lowered or "out of memory" in lowered:
			return _(
				"The model {0} needs more RAM than this machine has free. "
				"Pull a smaller model (for example llama3.2:3b or qwen2.5:3b), set it "
				"as the Model in AI HR Settings, or close other applications. "
				"Ollama said: {1}"
			).format(model, error)

		if "not found" in lowered or "no such model" in lowered:
			return _(
				"Ollama has no model named {0}. Pull it with `ollama pull {0}`, or set "
				"Model in AI HR Settings to one you already have.{1}"
			).format(model, self._installed_hint())

		return _("Ollama error: {0}").format(error)

	def _installed_hint(self) -> str:
		"""List the models actually available, so the fix is obvious."""
		try:
			tags = requests.get(f"{self.base_url}/api/tags", timeout=10).json()
			names = [m.get("name") for m in tags.get("models", []) if m.get("name")]
		except Exception:
			return ""
		if not names:
			return " " + _("No models are pulled yet.")
		return " " + _("Available: {0}").format(", ".join(names))

	def complete(self, system: str, prompt: str) -> AIResult:
		return self._send(system, prompt)

	def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> AIResult:
		# Local models follow a schema less reliably than hosted ones, so state the
		# contract in the prompt as well as constraining the decoder.
		return self._send(system, f"{prompt}\n\n{self._json_instruction(schema)}", schema=schema)
