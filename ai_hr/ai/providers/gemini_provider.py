"""Google Gemini adapter, built on the `google-genai` SDK."""

from __future__ import annotations

from typing import Any

from frappe import _

from ai_hr.ai.base import AIConfig, AIProvider, AIProviderError, AIResult


#: Keys that google-genai's `types.Schema` accepts. It is a pydantic model, so
#: anything else raises a ValidationError rather than being ignored - notably
#: `additionalProperties`, which ai_hr.ai.schemas sets for OpenAI strict mode.
_GEMINI_SCHEMA_KEYS = frozenset(
	{
		"type",
		"description",
		"nullable",
		"enum",
		"items",
		"properties",
		"required",
		"format",
		"title",
		"minimum",
		"maximum",
	}
)


def to_gemini_schema(node: Any) -> Any:
	"""Translate a JSON Schema into the dialect `types.Schema` expects.

	Two incompatibilities have to be bridged:

	* **Nullable types.** JSON Schema writes an optional string as
	  ``{"type": ["string", "null"]}``. Gemini's Schema takes a single type plus
	  a separate ``nullable`` flag, and rejects the list outright.
	* **Unsupported keys.** ``additionalProperties`` is meaningful to OpenAI's
	  strict mode but unknown to Schema, so it is dropped here instead of being
	  removed from the shared schemas (which would break OpenAI).

	Types are upper-cased because Schema validates them against an enum whose
	members are ``STRING``, ``NUMBER``, ``INTEGER`` and so on.
	"""
	if not isinstance(node, dict):
		return node

	out: dict[str, Any] = {}
	for key, value in node.items():
		if key not in _GEMINI_SCHEMA_KEYS:
			continue

		if key == "type":
			declared = value if isinstance(value, list) else [value]
			concrete = [t for t in declared if t != "null"]
			if len(declared) != len(concrete):
				out["nullable"] = True
			# A type of just ["null"] has no Gemini equivalent; treat it as a
			# nullable string so the field still round-trips.
			out["type"] = str(concrete[0] if concrete else "string").upper()
		elif key == "properties":
			out["properties"] = {k: to_gemini_schema(v) for k, v in (value or {}).items()}
		elif key == "items":
			out["items"] = to_gemini_schema(value)
		else:
			out[key] = value

	return out


class GeminiProvider(AIProvider):
	name = "Google Gemini"
	#: Pinned deliberately. The obvious alternative, `gemini-flash-latest`, never
	#: 404s but is markedly less available - measured 1/3 successful calls against
	#: 3/3 for this model, the rest failing with 503 UNAVAILABLE. A pinned model
	#: does eventually retire (that is what broke gemini-2.0-flash here), so
	#: `_explain` spells out the fix when it does. Override in AI HR Settings.
	default_model = "gemini-3.6-flash"

	#: Google returns 503 under load often enough that a single attempt is not
	#: reliable; the SDK's own retry does not always cover it.
	unavailable_retries = 2

	def __init__(self, config: AIConfig) -> None:
		super().__init__(config)
		self._client = None

	@property
	def client(self):
		if self._client is None:
			try:
				from google import genai
			except ImportError:
				raise AIProviderError(
					_("The 'google-genai' package is not installed. Run: bench pip install google-genai")
				)
			self._client = genai.Client(api_key=self._require_key())
		return self._client

	def _send(self, system: str, prompt: str, schema: dict[str, Any] | None = None) -> AIResult:
		config: dict[str, Any] = {
			"system_instruction": system,
			"max_output_tokens": self.config.max_tokens,
		}
		if schema is not None:
			config["response_mime_type"] = "application/json"
			# Translated, not passed through - see to_gemini_schema().
			config["response_schema"] = to_gemini_schema(schema)

		model = self.config.model or self.default_model

		import time

		last: Exception | None = None
		for attempt in range(self.unavailable_retries + 1):
			try:
				response = self.client.models.generate_content(
					model=model,
					contents=prompt,
					config=config,
				)
				break
			except Exception as exc:
				last = exc
				# Only capacity errors are worth repeating; a bad key or a retired
				# model will fail identically every time.
				if not self._is_transient(exc) or attempt == self.unavailable_retries:
					# The SDK raises vendor-specific errors; without this the UI
					# shows a bare "ClientError" and the reason is buried in the
					# traceback.
					raise AIProviderError(self._explain(exc, model)) from exc
				time.sleep(1.5 * (attempt + 1))
		else:  # pragma: no cover - the loop always breaks or raises
			raise AIProviderError(self._explain(last, model))

		usage = getattr(response, "usage_metadata", None)
		return AIResult(
			text=getattr(response, "text", "") or "",
			model=model,
			provider=self.name,
			input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
			output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
		)

	@staticmethod
	def _is_transient(exc: Exception) -> bool:
		"""True for errors that a retry could plausibly clear."""
		text = str(exc)
		return "UNAVAILABLE" in text or "503" in text or "500" in text

	def _explain(self, exc: Exception, model: str) -> str:
		"""Turn a Gemini API error into something an admin can act on."""
		text = str(exc)

		if "NOT_FOUND" in text or "404" in text:
			return _(
				"Gemini has no model named {0} (it may have been retired). "
				"Set Model in AI HR Settings to a current one, or clear it to use "
				"the default.{1}"
			).format(model, self._available_hint())

		if "API_KEY_INVALID" in text or "API key not valid" in text or "401" in text:
			return _("The Gemini API key in AI HR Settings was rejected. Check that it is correct.")

		if "UNAVAILABLE" in text or "503" in text:
			return _(
				"Gemini reported model {0} as overloaded and it did not recover after "
				"retrying. This is a temporary condition on Google's side - try again "
				"shortly, or set a different Model in AI HR Settings."
			).format(model)

		if "RESOURCE_EXHAUSTED" in text or "429" in text:
			return _("Gemini rate limit or quota reached. Wait and retry, or check your Google AI quota.")

		return _("Gemini error: {0}").format(text[:300])

	def _available_hint(self) -> str:
		"""List a few usable models, so the fix is obvious."""
		try:
			names = [
				m.name.replace("models/", "")
				for m in self.client.models.list()
				if "generateContent" in (getattr(m, "supported_actions", None) or ["generateContent"])
			]
		except Exception:
			return ""

		flash = sorted(n for n in names if "flash" in n and "preview" not in n)
		if not flash:
			return ""
		# models.list() also returns retired entries (gemini-2.5-flash is listed
		# but 404s), so this is phrased as a starting point, not a guarantee.
		return " " + _("Models listed for this key include: {0}").format(", ".join(flash[:5]))

	def complete(self, system: str, prompt: str) -> AIResult:
		return self._send(system, prompt)

	def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> AIResult:
		return self._send(system, prompt, schema=schema)
