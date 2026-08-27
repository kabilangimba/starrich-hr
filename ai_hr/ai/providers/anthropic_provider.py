"""Anthropic (Claude) adapter, built on the official `anthropic` SDK."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from ai_hr.ai.base import AIConfig, AIProvider, AIProviderError, AIResult

#: Beta flag for server-side refusal fallbacks. Claude API only.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(AIProvider):
	name = "Anthropic Claude"
	default_model = "claude-opus-5"

	def __init__(self, config: AIConfig) -> None:
		super().__init__(config)
		self._client = None

	@property
	def client(self):
		"""Lazily build the SDK client so importing this module never needs a key."""
		if self._client is None:
			try:
				import anthropic
			except ImportError:
				raise AIProviderError(
					_("The 'anthropic' package is not installed in this bench environment.")
				)

			kwargs: dict[str, Any] = {
				"api_key": self._require_key(),
				"timeout": float(self.config.timeout),
			}
			if self.config.base_url:
				kwargs["base_url"] = self.config.base_url
			self._client = anthropic.Anthropic(**kwargs)

		return self._client

	# -- request construction -------------------------------------------------

	def _output_config(self, schema: dict[str, Any] | None) -> dict[str, Any] | None:
		"""Build `output_config`, carrying effort and/or a JSON schema."""
		cfg: dict[str, Any] = {}
		if self.config.effort:
			cfg["effort"] = self.config.effort
		if schema is not None:
			cfg["format"] = {"type": "json_schema", "schema": schema}
		return cfg or None

	def _send(
		self, system: str, prompt: str, schema: dict[str, Any] | None = None
	) -> AIResult:
		"""One request, with server-side refusal fallback where available.

		Claude's safety classifiers can decline a request; that returns HTTP 200
		with `stop_reason == "refusal"` rather than raising. Requesting a fallback
		lets the API re-serve the request on another model in the same call. The
		beta is Claude-API-only and may not be enabled for every org, so a rejected
		beta degrades to a plain request instead of failing the job.
		"""
		params: dict[str, Any] = {
			"model": self.config.model or self.default_model,
			"max_tokens": self.config.max_tokens,
			"system": system,
			"messages": [{"role": "user", "content": prompt}],
		}

		output_config = self._output_config(schema)
		if output_config:
			params["output_config"] = output_config

		try:
			response = self.client.beta.messages.create(
				**params, betas=[FALLBACK_BETA], fallbacks="default"
			)
		except Exception as exc:
			# Only fall back for a rejected/unknown beta - never mask a real failure
			# such as an auth error, a rate limit, or a malformed schema.
			if not _is_unsupported_beta(exc):
				raise
			response = self.client.messages.create(**params)

		return self._to_result(response)

	def _to_result(self, response: Any) -> AIResult:
		"""Normalise an SDK response, checking `stop_reason` before reading text."""
		stop_reason = getattr(response, "stop_reason", None)

		if stop_reason == "refusal":
			details = getattr(response, "stop_details", None)
			category = getattr(details, "category", None) if details else None
			frappe.log_error(
				title="AI HR: Claude declined the request",
				message=f"model={getattr(response, 'model', '?')} category={category}",
			)
			raise AIProviderError(
				_("Claude declined this request on safety grounds. Category: {0}").format(
					category or _("unspecified")
				)
			)

		# `content` is a list of typed blocks; thinking blocks precede text ones.
		text = "".join(
			block.text
			for block in (getattr(response, "content", None) or [])
			if getattr(block, "type", None) == "text"
		)

		if stop_reason == "max_tokens" and not text.strip():
			raise AIProviderError(
				_(
					"Claude hit the token limit before producing an answer. "
					"Raise Max Tokens in AI HR Settings."
				)
			)

		usage = getattr(response, "usage", None)
		return AIResult(
			text=text,
			model=getattr(response, "model", self.config.model),
			provider=self.name,
			input_tokens=getattr(usage, "input_tokens", 0) or 0,
			output_tokens=getattr(usage, "output_tokens", 0) or 0,
			raw={"stop_reason": stop_reason},
		)

	# -- public API -----------------------------------------------------------

	def complete(self, system: str, prompt: str) -> AIResult:
		return self._send(system, prompt)

	def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> AIResult:
		# Claude enforces the schema natively, so the prompt carries no JSON
		# instructions - they would only compete with the constrained decoder.
		return self._send(system, prompt, schema=schema)


def _is_unsupported_beta(exc: Exception) -> bool:
	"""True when a request failed purely because the beta flag was not accepted."""
	if isinstance(exc, TypeError):
		# Older SDK builds have no `fallbacks` / `betas` kwarg at all.
		return True

	status = getattr(exc, "status_code", None)
	if status not in (400, 404):
		return False

	message = str(exc).lower()
	return any(hint in message for hint in ("beta", "fallback", "unexpected keyword"))
