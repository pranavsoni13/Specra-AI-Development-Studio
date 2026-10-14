from __future__ import annotations

import io
import zipfile

from app.core.document_export import render_document_export


SAMPLE = """# Software Requirements Specification: Demo
- Project ID: demo-001
- Document status: Draft

## Functional Requirements

- **FR-001** — Users can sign in securely.
- **FR-002** — Admins can manage project access.

### Notes

The report distinguishes generated content from verified implementation.
"""


def test_markdown_export_is_utf8_markdown():
    body, extension, media_type = render_document_export(SAMPLE, "md")
    assert extension == "md"
    assert media_type.startswith("text/markdown")
    assert body.startswith(b"# Software Requirements")


def test_pdf_export_is_a_real_pdf():
    body, extension, media_type = render_document_export(SAMPLE, "pdf")
    assert extension == "pdf"
    assert media_type == "application/pdf"
    assert body.startswith(b"%PDF-")
    assert len(body) > 500


def test_powerpoint_export_is_a_valid_pptx_package():
    body, extension, media_type = render_document_export(SAMPLE, "pptx")
    assert extension == "pptx"
    assert media_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert body.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert "ppt/presentation.xml" in archive.namelist()
        assert any(name.startswith("ppt/slides/slide") for name in archive.namelist())


def test_unsupported_export_format_is_rejected():
    try:
        render_document_export(SAMPLE, "pages")
    except ValueError as exc:
        assert "Unsupported document format" in str(exc)
    else:
        raise AssertionError("Unsupported format must not silently produce a file")
