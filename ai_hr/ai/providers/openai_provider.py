"""OpenAI adapter (Chat Completions, with strict structured outputs)."""

from __future__ import annotations

from typing import Any

from frappe import _

from ai_hr.ai.base import AIConfig, AIProvider, AIProviderError, AIResult


class OpenAIProvider(AIProvider):
	name = "OpenAI"
	default_model = "gpt-4o"

	def __init__(self, config: AIConfig) -> None:
		super().__init__(config)
		self._client = None

	@property
	def client(self):
		if self._client is None:
			try:
				from openai import OpenAI
			except ImportError:
				raise AIProviderError(
					_("The 'openai' package is not installed. Run: bench pip install openai")
				)
			kwargs: dict[str, Any] = {
				"api_key": self._require_key(),
				"timeout": float(self.config.timeout),
			}
			if self.config.base_url:
				kwargs["base_url"] = self.config.base_url
			self._client = OpenAI(**kwargs)
		return self._client

	def _send(self, system: str, prompt: str, response_format: dict | None = None) -> AIResult:
		kwargs: dict[str, Any] = {
			"model": self.config.model or self.default_model,
			"max_completion_tokens": self.config.max_tokens,
			"messages": [
				{"role": "system", "content": system},
				{"role": "user", "content": prompt},
			],
		}
		if response_format:
			kwargs["response_format"] = response_format

		response = self.client.chat.completions.create(**kwargs)
		choice = response.choices[0]

		if choice.finish_reason == "content_filter":
			raise AIProviderError(_("OpenAI blocked this request via its content filter."))

		usage = response.usage
		return AIResult(
			text=choice.message.content or "",
			model=response.model,
			provider=self.name,
			input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
			output_tokens=getattr(usage, "completion_tokens", 0) or 0,
			raw={"finish_reason": choice.finish_reason},
		)

	def complete(self, system: str, prompt: str) -> AIResult:
		return self._send(system, prompt)

	def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> AIResult:
		# `strict` requires every property to be required and additionalProperties
		# false; our schemas are authored that way in ai_hr.ai.schemas.
		return self._send(
			system,
			prompt,
			response_format={
				"type": "json_schema",
				"json_schema": {"name": "ai_hr_result", "strict": True, "schema": schema},
			},
		)
