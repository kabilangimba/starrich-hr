"""Provider-agnostic contract for AI calls.

Everything in `ai_hr` talks to this interface, never to a vendor SDK directly, so
adding a provider means adding one subclass and one registry entry (proposal §12).

All calls are server-side only. Credentials live in the `AI HR Settings` single and
are read through `get_api_key()`; they are never returned to a client (§15).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import frappe
from frappe import _


class AIProviderError(frappe.ValidationError):
	"""Raised when a provider cannot fulfil a request.

	Subclasses `frappe.ValidationError` so it surfaces as a clean message in the
	UI instead of a traceback, and is caught by Frappe's normal error handling.
	"""


@dataclass
class AIConfig:
	"""Resolved settings for one provider call.

	Built from `AI HR Settings` by `ai_hr.ai.registry.get_provider`. Holds the
	API key in memory for the duration of a single server-side call only.
	"""

	provider: str
	model: str
	api_key: str | None = None
	base_url: str | None = None
	max_tokens: int = 8000
	timeout: int = 180
	#: Reasoning depth, where the provider exposes one. `None` keeps the
	#: provider's own default rather than guessing a cost/quality tradeoff.
	effort: str | None = None


@dataclass
class AIResult:
	"""Normalised response, so callers never branch on which provider ran."""

	text: str
	model: str
	provider: str
	input_tokens: int = 0
	output_tokens: int = 0
	raw: dict[str, Any] = field(default_factory=dict)

	def as_json(self) -> dict[str, Any]:
		"""Parse `text` as JSON.

		Providers are asked for JSON via schema-constrained output where the API
		supports it, but not every provider guarantees it, so tolerate a fenced
		```json block and fall back to locating the outermost object.
		"""
		payload = (self.text or "").strip()

		if payload.startswith("```"):
			# Strip a ```json ... ``` fence, keeping the body intact.
			payload = payload.split("\n", 1)[-1] if "\n" in payload else payload
			if payload.rstrip().endswith("```"):
				payload = payload.rstrip()[: -len("```")]
			payload = payload.strip()

		try:
			return json.loads(payload)
		except json.JSONDecodeError:
			start, end = payload.find("{"), payload.rfind("}")
			if start != -1 and end > start:
				try:
					return json.loads(payload[start : end + 1])
				except json.JSONDecodeError:
					pass

		frappe.log_error(
			title="AI HR: provider returned non-JSON",
			message=f"provider={self.provider} model={self.model}\n\n{self.text[:4000]}",
		)
		raise AIProviderError(
			_("The AI provider returned a response that could not be read as JSON.")
		)


class AIProvider(ABC):
	"""Base class for every provider adapter."""

	#: Human-readable name, matched against the `provider` field in AI HR Settings.
	name: str = ""

	#: Used when the administrator has not pinned a model in settings.
	default_model: str = ""

	def __init__(self, config: AIConfig) -> None:
		self.config = config

	@abstractmethod
	def complete(self, system: str, prompt: str) -> AIResult:
		"""Return free-form text (job descriptions, interview summaries)."""
		raise NotImplementedError

	@abstractmethod
	def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> AIResult:
		"""Return JSON conforming to `schema` (CV parsing, scoring).

		Implementations should use the provider's native structured-output support
		where available and fall back to instructing the model in the prompt.
		"""
		raise NotImplementedError

	def _require_key(self) -> str:
		"""Fail early and legibly when the provider is unconfigured."""
		if not self.config.api_key:
			raise AIProviderError(
				_("No API key is configured for {0}. Set one in AI HR Settings.").format(
					self.name or self.config.provider
				)
			)
		return self.config.api_key

	@staticmethod
	def _json_instruction(schema: dict[str, Any]) -> str:
		"""Prompt-level JSON contract, for providers without schema enforcement."""
		return (
			"Respond with a single JSON object and nothing else - no prose, no code "
			"fence. It must conform to this JSON Schema:\n"
			f"{json.dumps(schema, indent=2)}"
		)
