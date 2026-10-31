"""bitra provider `claude`: bitra's own Anthropic adapter, with each role's answer schema made acceptable to
Claude's structured outputs.

bitra 0.10.2 sends the technical analyst's schema with numeric bounds (confidence has minimum 0 and maximum
1, horizon_bars minimum 1), and the Claude API refuses those with a 400 ("For 'number' type, properties
maximum, minimum are not supported"), so on the bundled `anthropic` provider that role never answers. This
provider sends the same schema with each bound moved into its field's description, as the Anthropic SDK's
own `transform_schema` does, and changes nothing else; bitra still checks every answer against the bounds
when it reads it (`_unit`, `_posint`). Installed beside bitra by setup.sh (`uv tool install ... --with`) and
found through bitra's provider entry point, so a desk names it as `provider = "claude"`.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trading_research_agents.llm.providers.anthropic import DEFAULT_MODEL, AnthropicCompleter
from trading_research_agents.llm.providers.registry import (
    DEFAULT_OPTIONS,
    CallOptions,
    Provider,
    _verify_anthropic,
)

BOUNDS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf")
NUMERIC = {"number", "integer"}
# Keys whose value maps names to schemas: the names are the caller's, never keywords to drop.
NAMED = ("properties", "$defs", "definitions")


def loosen(node: Any) -> Any:
    """The schema with every numeric bound moved into its field's description; the rest as it was."""
    if isinstance(node, list):
        return [loosen(v) for v in node]
    if not isinstance(node, Mapping):
        return node
    types = node.get("type")
    numeric = bool(NUMERIC & set(types if isinstance(types, list) else [types]))
    out: dict[str, Any] = {}
    moved: dict[str, Any] = {}
    for key, val in node.items():
        if numeric and key in BOUNDS:
            moved[key] = val
        elif key in NAMED and isinstance(val, Mapping):
            out[key] = {name: loosen(sub) for name, sub in val.items()}
        else:
            out[key] = loosen(val)
    if moved:
        note = "{" + ", ".join(f"{k}: {v}" for k, v in moved.items()) + "}"
        out["description"] = f"{out['description']}\n\n{note}" if out.get("description") else note
    return out


class ClaudeCompleter(AnthropicCompleter):
    def request(self, *, system: str, user: str, schema: Mapping[str, Any]) -> dict[str, Any]:
        return super().request(system=system, user=user, schema=loosen(schema))


def build(model: str | None, base_url: str | None, options: CallOptions = DEFAULT_OPTIONS) -> ClaudeCompleter:
    if base_url:
        raise ValueError("--base-url does not apply to the claude provider")
    return ClaudeCompleter(
        model or DEFAULT_MODEL,
        max_tokens=options.max_output_tokens,
        effort=options.effort,
        timeout_s=options.timeout_s,
        max_retries=options.max_retries,
    )


PROVIDER = Provider(
    "claude",
    "ANTHROPIC_API_KEY",
    DEFAULT_MODEL,
    False,
    build,
    "bitra's anthropic adapter with numeric bounds moved into descriptions",
    build,
    ("anthropic", "anthropic"),
    _verify_anthropic,
)
