"""SPI craft engines — headless tools that read and write engineering files.

Importing this package registers every tool in TOOL_REGISTRY.
"""
from .core import (TOOL_REGISTRY, ENGINE_VERSION, ToolResult, MissingData,
                   InvalidInput, LocalStorage, tool_schemas)
from . import grid  # noqa: F401  (registers grid.* tools)

__all__ = ["TOOL_REGISTRY", "ENGINE_VERSION", "ToolResult", "MissingData",
           "InvalidInput", "LocalStorage", "tool_schemas"]
__version__ = "0.1.0"
