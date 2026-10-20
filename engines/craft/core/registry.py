"""TOOL_REGISTRY: the only surface the AI orchestrator sees.

A tool is registered with a pydantic input model. GET /tools emits JSON schemas
from those models, so the orchestrator plans calls against schemas and never
against Python signatures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from pydantic import BaseModel

Engine = Literal["grid", "word", "cad", "pdf"]
Mode = Literal["preview", "commit"]


@dataclass
class ToolSpec:
    name: str
    engine: Engine
    fn: Callable[..., Any]
    input_model: type[BaseModel]
    summary: str
    modes: tuple[Mode, ...] = ("preview", "commit")
    #: Phase-2 stubs stay registered so GET /tools is honest about what exists.
    implemented: bool = True


TOOL_REGISTRY: dict[str, ToolSpec] = {}


def register(name: str, engine: Engine, input_model: type[BaseModel], summary: str,
             modes: tuple[Mode, ...] = ("preview", "commit"), implemented: bool = True):
    def deco(fn):
        if name in TOOL_REGISTRY:
            raise RuntimeError(f"Tool already registered: {name}")
        TOOL_REGISTRY[name] = ToolSpec(name, engine, fn, input_model, summary, modes, implemented)
        return fn
    return deco


def tool_schemas() -> list[dict]:
    return [
        {
            "name": s.name,
            "engine": s.engine,
            "summary": s.summary,
            "modes": list(s.modes),
            "implemented": s.implemented,
            "input_schema": s.input_model.model_json_schema(),
        }
        for s in sorted(TOOL_REGISTRY.values(), key=lambda s: s.name)
    ]
