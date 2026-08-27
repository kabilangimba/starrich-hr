"""Provider registry and factory.

`AI HR Settings` names a provider; this module turns that name into a configured
adapter. Adding a provider means adding one entry to `PROVIDERS` (§12, §23).
"""

from __future__ import annotations

import frappe
from frappe import _

from ai_hr.ai.base import AIConfig, AIProvider, AIProviderError
from ai_hr.ai.providers.anthropic_provider import AnthropicProvider
from ai_hr.ai.providers.gemini_provider import GeminiProvider
from ai_hr.ai.providers.ollama_provider import OllamaProvider
from ai_hr.ai.providers.openai_provider import OpenAIProvider

#: Maps the `provider` Select option in AI HR Settings to its adapter.
PROVIDERS: dict[str, type[AIProvider]] = {
	"Anthropic Claude": AnthropicProvider,
	"OpenAI": OpenAIProvider,
	"Google Gemini": GeminiProvider,
	"Ollama": OllamaProvider,
}

SETTINGS_DOCTYPE = "AI HR Settings"


def get_settings():
	"""Return the cached AI HR Settings single."""
	return frappe.get_cached_doc(SETTINGS_DOCTYPE)


def get_provider(settings=None) -> AIProvider:
	"""Build the configured provider.

	The API key is read server-side via `get_password` and lives only in the
	returned adapter for the duration of the call - it is never sent to a client
	and never written to a log (§15).
	"""
	settings = settings or get_settings()

	provider_name = (settings.provider or "").strip()
	adapter = PROVIDERS.get(provider_name)
	if not adapter:
		raise AIProviderError(
			_("Unknown AI provider {0}. Choose one of: {1}").format(
				provider_name or _("(not set)"), ", ".join(PROVIDERS)
			)
		)

	# Ollama runs locally and needs no credential.
	api_key = None
	if provider_name != "Ollama":
		api_key = settings.get_password("api_key", raise_exception=False)

	config = AIConfig(
		provider=provider_name,
		model=(settings.model or "").strip() or adapter.default_model,
		api_key=api_key,
		base_url=(settings.base_url or "").strip() or None,
		max_tokens=int(settings.max_tokens or 8000),
		timeout=int(settings.request_timeout or 180),
		effort=(getattr(settings, "effort", "") or "").strip() or None,
	)
	return adapter(config)


def require_feature(flag: str) -> None:
	"""Raise unless the named feature toggle is enabled in settings (§12)."""
	settings = get_settings()
	if not settings.get(flag):
		raise AIProviderError(
			_("This AI feature is disabled. Enable it in AI HR Settings.")
		)
