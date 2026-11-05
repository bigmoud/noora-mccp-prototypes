"""One way to call Claude, shared by the extractor, the judge and the Copilot.

Every call: forced single tool (JSON out, no other abilities), hard spend cap checked
first, spend recorded after, at most one retry.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import settings

_ledger_lock = threading.Lock()


def spend_so_far() -> float:
    try:
        return float(json.loads(settings.spend_ledger.read_text())["usd"])
    except (OSError, ValueError, KeyError):
        return 0.0


# List prices per million tokens (input, output), Nov 2026. Haiku: prompts under 100k tokens.
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00)}


def price(model: str) -> tuple[float, float]:
    if model == settings.extractor_model and settings.price_in_per_mtok is not None:
        return settings.price_in_per_mtok, settings.price_out_per_mtok or 0
    return PRICES.get(model, (2.00, 10.00))  # unknown model: assume the dearer price


def cost(model: str, tin: int, tout: int) -> float:
    pin, pout = price(model)
    return tin / 1e6 * pin + tout / 1e6 * pout


def _record_spend(tin: int, tout: int, model: str = "") -> None:
    usd = cost(model or settings.extractor_model, tin, tout)
    with _ledger_lock:
        try:
            calls = json.loads(settings.spend_ledger.read_text()).get("calls", 0) + 1
        except (OSError, ValueError):
            calls = 1
        data = {"usd": spend_so_far() + usd, "calls": calls}
        settings.spend_ledger.parent.mkdir(parents=True, exist_ok=True)
        settings.spend_ledger.write_text(json.dumps(data))


@dataclass
class ToolCall:
    output: dict | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    ms: int = 0
    error: str = ""


_NO_FORCED_TOOL: set[str] = set()  # models that reject a forced tool_choice


def call_tool(system: str, user: str, tool: dict, model: str, max_tokens: int = 800) -> ToolCall:
    out = _call(system, user, tool, model, max_tokens, forced=model not in _NO_FORCED_TOOL)
    if "tool_choice" in out.error and "not supported" in out.error:
        _NO_FORCED_TOOL.add(model)
        out = _call(system, user, tool, model, max_tokens, forced=False)
    return out


def _call(system: str, user: str, tool: dict, model: str, max_tokens: int, forced: bool) -> ToolCall:
    out = ToolCall()
    if not settings.anthropic_api_key:
        out.error = "no API key"
        return out
    if spend_so_far() >= settings.spend_cap_usd:
        out.error = f"spend cap reached (${settings.spend_cap_usd:.2f}): no call made"
        return out
    if not forced:  # the model may answer in text; code treats a missing tool call as "no answer"
        system += f"\n\nAlways answer by calling the {tool['name']} tool exactly once. Never answer in plain text."
    body = {"model": model, "max_tokens": max_tokens, "system": system, "tools": [tool],
            "tool_choice": {"type": "tool", "name": tool["name"]} if forced else {"type": "auto"},
            "messages": [{"role": "user", "content": user}]}
    headers = {"content-type": "application/json", "x-api-key": settings.anthropic_api_key,
               "anthropic-version": "2023-06-01"}
    if settings.anthropic_workspace_id:
        headers["anthropic-workspace-id"] = settings.anthropic_workspace_id
    t0 = time.time()
    data = None
    for attempt in range(2):  # one retry at most
        try:
            req = urllib.request.Request(settings.anthropic_base_url + "/v1/messages",
                                         data=json.dumps(body).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error", {}).get("message", "")[:160]
            except Exception:
                msg = ""
            out.error = f"HTTP {e.code} {msg}".strip()
            if e.code not in (429, 500, 502, 503, 529) or attempt == 1:
                break
            time.sleep(2)
        except Exception as e:
            out.error = type(e).__name__
            break
    out.ms = int((time.time() - t0) * 1000)
    if data is None:
        return out
    out.error = ""
    usage = data.get("usage", {})
    out.tokens_in = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
    out.tokens_out = usage.get("output_tokens", 0)
    _record_spend(out.tokens_in, out.tokens_out, model)
    out.output = next((b.get("input") for b in data.get("content", []) if b.get("type") == "tool_use"), None)
    if data.get("stop_reason") == "max_tokens":
        out.output, out.error = None, "answer cut off (max_tokens)"  # never use a half-written answer
    elif not isinstance(out.output, dict) or not out.output:
        out.output, out.error = None, "no tool output"
    return out
