"""WordCraft: fill a .docx template.

A placeholder with no supplied value is never blanked and never guessed. The
document is not written at all: a transmittal that reads "Project: " is worse
than no transmittal, because it will be sent.
"""
from __future__ import annotations

import io
import time

import docx
from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, MissingItem, OutputFile,
                    Storage, ToolResult, register, sha256)
from . import placeholders

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class FillInput(BaseModel):
    template_key: str = Field(description="storage key of the .docx template")
    values: dict[str, str]
    output_key: str | None = None
    output_name: str = "document.docx"
    allow_unfilled: bool = Field(
        False,
        description="write the file even with placeholders left in it. Off by "
                    "default; only for drafts that will not be issued.")


@register("word.fill_template", "word", FillInput,
          "Fill a .docx template's {{placeholders}} from supplied values")
def fill_template(data: FillInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="word.fill_template", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("word.fill_template needs storage to fetch the template")

    try:
        doc = docx.Document(io.BytesIO(storage.read(data.template_key)))
    except Exception as e:                       # noqa: BLE001
        raise InvalidInput(
            f"{data.template_key} is not a readable .docx: {e}. A .doc (Word 97) "
            "must be converted first.") from e

    expected = placeholders.scan(doc)
    used, remaining = placeholders.fill(doc, data.values)
    unknown = sorted(set(data.values) - expected)

    res.outputs = {
        "placeholders_in_template": sorted(expected),
        "filled": sorted(used),
        "unfilled": sorted(remaining),
        "values_not_used_by_template": unknown,
    }

    if remaining and not data.allow_unfilled:
        res.status = "missing_data"
        res.missing = [
            MissingItem(field=key, record=f"template:{data.template_key}",
                        note=f"The template contains {{{{{key}}}}} and no value was "
                             "supplied. No file was written: an issued document "
                             "with a blank or a literal placeholder in it is worse "
                             "than none.")
            for key in sorted(remaining)
        ]
        res.duration_ms = int((time.perf_counter() - started) * 1000)
        return res

    if remaining:
        res.warnings.append(
            "Written with " + str(len(remaining)) + " placeholder(s) still in the "
            "text (" + ", ".join(sorted(remaining)) + ") because allow_unfilled "
            "was set. Do not issue this file.")
    if unknown:
        res.warnings.append(
            "These values were supplied but the template has no placeholder for "
            "them: " + ", ".join(unknown) + ". Check for a typo in the key.")

    buf = io.BytesIO()
    doc.save(buf)
    payload = buf.getvalue()
    key = data.output_key or f"craft/documents/{data.output_name}"
    storage.write(key, payload)

    res.files = [OutputFile(name=data.output_name, mime=DOCX_MIME, storage_key=key,
                            byte_size=len(payload), sha256=sha256(payload))]
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
