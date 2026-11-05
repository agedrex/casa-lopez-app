"""Pure rules of the supplier documents (no database, no network): file checks and the OCR state machine."""

import hashlib
import logging
from datetime import date
from decimal import Decimal as D

import pytest

from backend import proveedores
from backend.models import DocumentoProveedor
from backend.ocr_llm import OcrError, OcrResult, OcrSuggestion
from backend.servicios import DatosInvalidos

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 20
PDF = b"%PDF-1.7\n" + b"\x00" * 20
SECRET = "sk-ant-api03-SECRET-THAT-MUST-NOT-LEAK"


# --- magic bytes (S3): the content decides, never the declared mime or the extension ------------------------------

@pytest.mark.parametrize("content, mime", [
    (JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp"), (PDF, "application/pdf"),
])
def test_the_type_comes_from_the_magic_bytes(content, mime):
    assert proveedores.detect_mime(content) == mime


@pytest.mark.parametrize("content", [
    b"", b"MZ\x90\x00 this is a windows executable", b"<html><script>alert(1)</script></html>",
    b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", b"GIF89a....",
    b"RIFF\x24\x00\x00\x00WAVEfmt ", b"\x89PNG", b"  %PDF-1.7", b"PK\x03\x04 zip",
])
def test_anything_else_is_not_a_document(content):
    assert proveedores.detect_mime(content) is None


@pytest.mark.parametrize("content, filename, declared", [
    (b"MZ\x90\x00 executable", "factura.pdf", "application/pdf"),
    (b"<html>x</html>", "foto.png", "image/png"),
    (b"#!/bin/sh\nrm -rf /", "foto.jpg", "image/jpeg"),
])
def test_a_spoofed_mime_or_extension_is_refused_in_spanish(content, filename, declared):
    with pytest.raises(DatosInvalidos) as error:
        proveedores.validate_file(content)
    assert "JPG, PNG, WebP o PDF" in str(error.value)


def test_validate_file_returns_the_detected_mime_and_the_sha256():
    mime, digest = proveedores.validate_file(PNG)
    assert mime == "image/png" and digest == hashlib.sha256(PNG).hexdigest()


def test_the_same_bytes_give_the_same_digest_and_other_bytes_another():
    assert proveedores.validate_file(PNG)[1] == proveedores.validate_file(PNG)[1]
    assert proveedores.validate_file(PNG)[1] != proveedores.validate_file(PNG + b"1")[1]


def test_an_empty_file_is_refused():
    with pytest.raises(DatosInvalidos) as error:
        proveedores.validate_file(b"")
    assert "vacío" in str(error.value)


def test_the_limit_is_10_mb():
    assert proveedores.MAX_FILE_BYTES == 10 * 1024 * 1024
    big = PNG + b"\x00" * proveedores.MAX_FILE_BYTES
    with pytest.raises(proveedores.ArchivoMuyGrande) as error:
        proveedores.validate_file(big)
    assert "10 MB" in str(error.value)
    assert proveedores.validate_file(PNG + b"\x00" * (proveedores.MAX_FILE_BYTES - len(PNG)))[0] == "image/png"


# --- sanitized filename: a label, never a path --------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("factura.pdf", "factura.pdf"),
    ("../../etc/passwd", "passwd"),
    ("C:\\Users\\x\\factura 1.pdf", "factura 1.pdf"),
    ("/var/tmp/x.png", "x.png"),
    ("factura\x00.pdf", "factura.pdf"),
    ("fac\ntura\r.pdf", "factura.pdf"),
    (".hidden", "hidden"),
    ("...", "archivo"),
    ("", "archivo"),
    (None, "archivo"),
    ("   ", "archivo"),
    ("Factura Rouez – setiembre ñandú.pdf", "Factura Rouez – setiembre ñandú.pdf"),
    ('a"b<c>d|e?f*g.pdf', "a_b_c_d_e_f_g.pdf"),
    ("a    b.pdf", "a b.pdf"),
])
def test_filename_is_sanitized(raw, expected):
    assert proveedores.sanitize_filename(raw) == expected


def test_filename_is_cut_to_120_characters_keeping_the_extension():
    cleaned = proveedores.sanitize_filename("x" * 300 + ".pdf")
    assert len(cleaned) <= 120 and cleaned.endswith(".pdf")


# --- download headers (S5) -----------------------------------------------------------------------------------------

def test_images_open_inline_and_the_pdf_downloads():
    inline = proveedores.file_headers("image/png", "foto.png")
    assert inline["Content-Disposition"].startswith("inline;")
    attachment = proveedores.file_headers("application/pdf", "factura.pdf")
    assert attachment["Content-Disposition"].startswith("attachment;")
    for headers in (inline, attachment):
        assert headers["X-Content-Type-Options"] == "nosniff"


def test_the_filename_in_the_header_cannot_break_out_of_it():
    headers = proveedores.file_headers("image/png", 'a"; filename=evil.exe\r\nX-Evil: 1')
    disposition = headers["Content-Disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    assert 'evil.exe"' not in disposition.replace("filename*=UTF-8''", "")
    assert all("\n" not in value and "\r" not in value for value in headers.values())


def test_non_ascii_names_use_the_rfc5987_form():
    disposition = proveedores.file_headers("image/png", "ñandú.png")["Content-Disposition"]
    assert "filename*=UTF-8''%C3%B1and%C3%BA.png" in disposition


# --- OCR state machine (S4), on the object, no database ------------------------------------------------------------

class FakeOcr:
    def __init__(self, result=None, error=None):
        self.result = result or OcrResult(
            text="FACTURA A\nTotal $ 1.234,50",
            suggestion=OcrSuggestion(numero="0001-1", fecha=date(2026, 9, 3), total=D("1234.50"), moneda="ARS"))
        self.error = error
        self.calls = []

    def read(self, content, mime):
        self.calls.append((content, mime))
        if self.error:
            raise self.error
        return self.result


def document(**changes):
    values = dict(nombre_archivo="f.png", mime="image/png", contenido=PNG, tamano_bytes=len(PNG), ocr_estado="PENDIENTE")
    values.update(changes)
    return DocumentoProveedor(**values)


def test_a_good_read_is_listo_with_text_and_a_suggestion_but_the_typed_data_is_untouched():
    doc = document(numero="A-7", total=D("5"), moneda="USD", ocr_error="old")
    ocr = FakeOcr()
    proveedores.apply_ocr(doc, ocr)
    assert ocr.calls == [(PNG, "image/png")]
    assert doc.ocr_estado == "LISTO" and doc.ocr_error is None
    assert doc.ocr_texto.startswith("FACTURA A")
    assert doc.ocr_sugerencia == {"numero": "0001-1", "fecha": "2026-09-03", "total": "1234.50", "moneda": "ARS"}
    # the OCR only suggests: what a person typed is never replaced
    assert (doc.numero, doc.total, doc.moneda, doc.fecha_documento) == ("A-7", D("5"), "USD", None)


def test_the_suggestion_total_is_a_string_not_a_float():
    doc = document()
    proveedores.apply_ocr(doc, FakeOcr())
    assert isinstance(doc.ocr_sugerencia["total"], str)


def test_without_a_client_the_state_is_no_configurado_and_the_file_is_kept():
    doc = document()
    proveedores.apply_ocr(doc, None)
    assert doc.ocr_estado == "NO_CONFIGURADO" and doc.contenido == PNG and doc.ocr_texto is None


def test_a_provider_failure_is_error_with_the_safe_message_only():
    doc = document()
    proveedores.apply_ocr(doc, FakeOcr(error=OcrError("El OCR tardó demasiado.", "timeout")))
    assert doc.ocr_estado == "ERROR" and doc.ocr_error == "El OCR tardó demasiado." and doc.contenido == PNG
    assert doc.ocr_texto is None and doc.ocr_sugerencia is None


def test_an_unexpected_failure_is_error_with_a_generic_message_never_the_raw_text(caplog):
    doc = document()
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        proveedores.apply_ocr(doc, FakeOcr(error=RuntimeError(f"boom {SECRET}")))
    assert doc.ocr_estado == "ERROR" and SECRET not in doc.ocr_error and doc.ocr_error == proveedores.MESSAGE_OCR_FAILED
    assert SECRET not in caplog.text and "RuntimeError" in caplog.text


def test_a_retry_after_an_error_clears_the_error_and_stores_the_new_result():
    doc = document(ocr_estado="ERROR", ocr_error="El OCR tardó demasiado.")
    proveedores.apply_ocr(doc, FakeOcr())
    assert doc.ocr_estado == "LISTO" and doc.ocr_error is None


def test_a_retry_that_fails_again_keeps_the_previous_text_out_of_the_error_state():
    doc = document(ocr_estado="LISTO", ocr_texto="viejo", ocr_sugerencia={"numero": "1"})
    proveedores.apply_ocr(doc, FakeOcr(error=OcrError("No se pudo leer ahora.", "red")))
    assert doc.ocr_estado == "ERROR"
    assert doc.ocr_texto == "viejo"  # a failed retry never destroys what a good read already stored


# --- typed data: a total needs its currency ------------------------------------------------------------------------

def test_a_total_without_currency_is_refused():
    with pytest.raises(DatosInvalidos) as error:
        proveedores.validate_amounts(D("10"), None)
    assert "moneda" in str(error.value)


@pytest.mark.parametrize("total, currency", [(None, None), (None, "ARS"), (D("0"), "ARS"), (D("10.5"), "USD")])
def test_valid_total_and_currency_pairs(total, currency):
    proveedores.validate_amounts(total, currency)


def test_a_negative_total_is_refused():
    with pytest.raises(DatosInvalidos):
        proveedores.validate_amounts(D("-1"), "ARS")
