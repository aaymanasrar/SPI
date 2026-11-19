"""FastAPI surface. The AI orchestrator sees GET /tools and nothing else.

Mode enforcement lives on the Next.js side, where the session is: craft.preview
for preview, craft.commit for commit. This service trusts its caller, so it must
never be exposed outside the server network.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError

from .core import (ENGINE_VERSION, InvalidInput, LocalStorage, MissingData,
                   TOOL_REGISTRY, ToolResult, ToolUnavailable, tool_schemas)
# Importing craft registers every engine's tools; importing one engine would
# serve a registry missing the others.
from . import grid, pdf, cad, word, bim, review  # noqa: F401  (registration side-effect)

app = FastAPI(title="SPI Craft Engines", version=ENGINE_VERSION)


class ToolCall(BaseModel):
    mode: str = "preview"
    input: dict[str, Any] = {}
    storage_root: str | None = None
    operation_id: str | None = None


@app.get("/health")
def health() -> dict:
    from .review import ai
    cfg = ai.config()
    return {"status": "ok", "engine_version": ENGINE_VERSION,
            "tools": len(TOOL_REGISTRY),
            # Which language model reads specs, if any. Never a key or a secret.
            "ai": {"provider": cfg["provider"], "model": cfg["model"],
                   "skill_version": ai.skill()[1]} if cfg else None}


@app.get("/tools")
def list_tools() -> list[dict]:
    return tool_schemas()


@app.post("/tools/{name}")
def run_tool(name: str, call: ToolCall) -> dict:
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        raise HTTPException(404, f"No such tool: {name}")
    if not spec.implemented:
        raise HTTPException(501, f"{name} is declared but not implemented (phase 2)")
    if call.mode not in spec.modes:
        raise HTTPException(400, f"{name} does not support mode {call.mode!r}; "
                                 f"supported: {list(spec.modes)}")

    started = time.perf_counter()
    try:
        payload = spec.input_model.model_validate(call.input)
    except ValidationError as e:
        return ToolResult(operation_id=call.operation_id, tool=name,
                          status="invalid_input",
                          warnings=[e.json()],
                          duration_ms=int((time.perf_counter() - started) * 1000)
                          ).model_dump()

    storage = LocalStorage(call.storage_root) if call.storage_root else None
    try:
        result: ToolResult = spec.fn(payload, storage=storage)
    except MissingData as e:
        result = ToolResult(tool=name, status="missing_data",
                            missing=[{"field": i.get("field", "?"),
                                      "record": i.get("record", "?"),
                                      "note": i.get("note")} for i in e.items])
    except ToolUnavailable as e:
        # The request was valid; this machine is missing a program. Say which.
        result = ToolResult(tool=name, status="error", error=str(e))
    except InvalidInput as e:
        result = ToolResult(tool=name, status="invalid_input", warnings=[str(e)])
    except Exception as e:                      # noqa: BLE001 — surfaced, not swallowed
        # `error` is set, not just `warnings`: migration 0023 constrains
        # (status = 'error') = (error is not null), so a null here would make the
        # craft_operations insert fail and lose the record of the failure.
        result = ToolResult(tool=name, status="error",
                            error=f"{type(e).__name__}: {e}")

    result.operation_id = call.operation_id
    if result.duration_ms is None:
        result.duration_ms = int((time.perf_counter() - started) * 1000)
    return result.model_dump()
