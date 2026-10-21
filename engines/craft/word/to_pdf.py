"""WordCraft: convert .docx to PDF with LibreOffice headless.

LibreOffice is MPL-2.0 and is invoked as a SEPARATE PROCESS, which is the
condition the licence policy attaches to MPL. Nothing is linked into this
package.

If it is not installed the tool says so and names the program. It does not fall
back to a different renderer: a submittal that silently loses its letterhead
because a fallback engine ignored the template's styles is a worse failure than
a clear refusal.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, OutputFile, Storage,
                    ToolResult, ToolUnavailable, register, sha256)

CANDIDATES = (
    "soffice", "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice", "/usr/lib/libreoffice/program/soffice",
)


def find_soffice() -> str | None:
    env = os.environ.get("SOFFICE_PATH")
    if env and Path(env).exists():
        return env
    for c in CANDIDATES:
        found = shutil.which(c) if not c.startswith("/") else (c if Path(c).exists() else None)
        if found:
            return found
    return None


class ToPdfInput(BaseModel):
    storage_key: str = Field(description="storage key of the .docx to convert")
    output_key: str | None = None
    output_name: str = "document.pdf"
    timeout_seconds: int = 120


@register("word.to_pdf", "word", ToPdfInput,
          "Convert a .docx to PDF using LibreOffice headless (separate process)")
def to_pdf(data: ToPdfInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="word.to_pdf", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("word.to_pdf needs storage to fetch the document")

    soffice = find_soffice()
    if soffice is None:
        raise ToolUnavailable(
            "LibreOffice is not installed on this machine, so .docx cannot be "
            "converted to PDF. Install it (macOS: brew install --cask "
            "libreoffice; Debian: apt-get install libreoffice-writer), or set "
            "SOFFICE_PATH to the soffice binary. The .docx itself is unaffected.")

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "input.docx"
        src.write_bytes(storage.read(data.storage_key))
        # -env:UserInstallation isolates the profile: two concurrent conversions
        # sharing the default profile make the second one exit silently.
        proc = subprocess.run(
            [soffice, "--headless", "--norestore",
             f"-env:UserInstallation=file://{tmp}/profile",
             "--convert-to", "pdf", "--outdir", tmp, str(src)],
            capture_output=True, timeout=data.timeout_seconds, check=False)
        out = Path(tmp) / "input.pdf"
        if not out.exists():
            raise ToolUnavailable(
                "LibreOffice ran but produced no PDF (exit "
                f"{proc.returncode}). stderr: "
                f"{proc.stderr.decode('utf-8', 'replace')[:400]}")
        payload = out.read_bytes()

    key = data.output_key or f"craft/documents/{data.output_name}"
    storage.write(key, payload)
    res.files = [OutputFile(name=data.output_name, mime="application/pdf",
                            storage_key=key, byte_size=len(payload),
                            sha256=sha256(payload))]
    res.outputs = {"converted_from": data.storage_key, "converter": soffice}
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
