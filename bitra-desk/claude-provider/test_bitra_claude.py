"""Tests for the bitra `claude` provider. They need bitra installed beside the plugin:
python3 -m venv /tmp/bv && /tmp/bv/bin/pip install ./bitra-desk/claude-provider
/tmp/bv/bin/python -m unittest discover -s bitra-desk/claude-provider -p 'test_*.py' -v
"""
from __future__ import annotations

import copy
import json
import unittest

import bitra_claude
from trading_research_agents.agents.technical_analyst.role import SCHEMA as TECHNICAL
from trading_research_agents.llm.providers.registry import provider


def bounds_left(node) -> list[str]:
    """Every numeric bound still in the schema, by where it sits."""
    found = []

    def walk(n, path):
        if isinstance(n, dict):
            types = n.get("type")
            if set(types if isinstance(types, list) else [types]) & {"number", "integer"}:
                found.extend(f"{path}.{k}" for k in bitra_claude.BOUNDS if k in n)
            for k, v in n.items():
                walk(v, f"{path}.{k}")
        elif isinstance(n, list):
            for i, v in enumerate(n):
                walk(v, f"{path}[{i}]")

    walk(node, "$")
    return found


class LoosenTest(unittest.TestCase):
    def test_technical_schema_loses_its_bounds_and_nothing_else(self):
        self.assertTrue(bounds_left(TECHNICAL))  # what the API refused on 31 Oct 2026
        before = copy.deepcopy(TECHNICAL)
        got = bitra_claude.loosen(TECHNICAL)
        self.assertEqual(bounds_left(got), [])
        self.assertEqual(TECHNICAL, before)  # bitra's own schema is not changed in place
        conf = got["properties"]["confidence"]
        self.assertEqual(conf, {"type": "number", "description": "{minimum: 0, maximum: 1}"})
        self.assertEqual(got["properties"]["horizon_bars"]["description"], "{minimum: 1}")
        self.assertEqual(got["properties"]["stop_price"], {"type": ["number", "null"]})
        self.assertEqual((got["required"], got["additionalProperties"]), (TECHNICAL["required"], False))
        self.assertEqual(got["properties"]["setup"], TECHNICAL["properties"]["setup"])

    def test_a_property_named_like_a_keyword_is_kept(self):
        schema = {"type": "object", "properties": {"minimum": {"type": "number", "maximum": 5, "description": "x"}}}
        got = bitra_claude.loosen(schema)
        self.assertEqual(got["properties"], {"minimum": {"type": "number", "description": "x\n\n{maximum: 5}"}})

    def test_non_numeric_bounds_are_left_alone(self):
        schema = {"type": "array", "items": {"type": "string"}, "minItems": 1}
        self.assertEqual(bitra_claude.loosen(schema), schema)


class ProviderTest(unittest.TestCase):
    def test_registered_through_the_entry_point(self):
        p = provider("claude")
        self.assertIs(p, bitra_claude.PROVIDER)
        self.assertEqual((p.key_env, p.default_model), ("ANTHROPIC_API_KEY", "claude-opus-5-5"))

    def test_request_is_the_bundled_one_with_the_loosened_schema(self):
        c = bitra_claude.build("claude-opus-5-5", None)
        req = c.request(system="doctrine", user="idea", schema=TECHNICAL)
        self.assertEqual(req["model"], "claude-opus-5-5")
        self.assertEqual(req["output_config"]["format"]["schema"], bitra_claude.loosen(TECHNICAL))
        self.assertEqual(req["output_config"]["effort"], "high")
        self.assertEqual(req["system"][0]["cache_control"], {"type": "ephemeral"})
        json.dumps(req)  # what the SDK will serialize


if __name__ == "__main__":
    unittest.main()
