import importlib.util
import os
import sys
from pathlib import Path
import zipfile
from io import BytesIO

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPLITTER_PATH = ROOT / "app" / "splitter.py"

spec = importlib.util.spec_from_file_location("app.splitter", SPLITTER_PATH)
assert spec and spec.loader
splitter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = splitter
spec.loader.exec_module(splitter)

split_docx_by_size = splitter.split_docx_by_size
DocxSplitError = splitter.DocxSplitError


CONTENT_TYPES = """<?xml version='1.0' encoding='UTF-8'?>
<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>
  <Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>
  <Default Extension='xml' ContentType='application/xml'/>
  <Default Extension='png' ContentType='image/png'/>
  <Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>
</Types>
"""

RELS = """<?xml version='1.0' encoding='UTF-8'?>
<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>
  <Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/>
</Relationships>
"""


SECT_PR = """
<w:sectPr>
  <w:pgSz w:w='12240' w:h='15840'/>
  <w:pgMar w:top='1440' w:right='1440' w:bottom='1440' w:left='1440' w:header='720' w:footer='720' w:gutter='0'/>
</w:sectPr>
"""


def build_paragraph(text: str, include_page_break: bool = False) -> str:
    page_break = ""
    if include_page_break:
        page_break = "<w:r><w:br w:type='page'/></w:r>"
    return (
        "<w:p>"
        "<w:r><w:t xml:space='preserve'>" + text + "</w:t></w:r>"
        f"{page_break}"
        "</w:p>"
    )


def build_document_xml(paragraphs: list[str]) -> bytes:
    body = "".join(paragraphs) + SECT_PR
    xml = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main' "
        "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'>"
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    return xml.encode("utf-8")


def create_docx(
    paragraphs: list[str],
    extra_files: dict[str, bytes] | None = None,
) -> bytes:
    document_xml = build_document_xml(paragraphs)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELS)
        archive.writestr("word/document.xml", document_xml)
        if extra_files:
            for name, data in extra_files.items():
                archive.writestr(name, data)
    buffer.seek(0)
    return buffer.getvalue()


def extract_document_xml(docx_bytes: bytes) -> str:
    with zipfile.ZipFile(BytesIO(docx_bytes)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def test_split_uses_page_breaks_for_chunk_boundaries(tmp_path):
    docx_bytes = create_docx(
        [
            build_paragraph("첫 번째 페이지" + "A" * 4000, include_page_break=True),
            build_paragraph("두 번째 페이지" + "B" * 4000),
        ]
    )

    result = split_docx_by_size(docx_bytes, target_size_mb=0.00102, original_name="매뉴얼.docx")

    assert result.total_pages == 2
    assert len(result.chunks) == 2

    first_chunk, second_chunk = result.chunks
    assert first_chunk.filename == "매뉴얼_01_01.docx"
    assert second_chunk.filename == "매뉴얼_02_02.docx"

    first_xml = extract_document_xml(first_chunk.data)
    second_xml = extract_document_xml(second_chunk.data)

    assert "첫 번째 페이지" in first_xml
    assert "두 번째 페이지" not in first_xml
    assert "두 번째 페이지" in second_xml


def test_split_raises_for_invalid_target_size():
    docx_bytes = create_docx([build_paragraph("내용")])

    with pytest.raises(ValueError):
        split_docx_by_size(docx_bytes, target_size_mb=0, original_name="invalid.docx")


def test_split_limits_chunk_size_when_possible():
    paragraphs = []
    for idx in range(5):
        include_break = idx < 4
        text = f"페이지{idx} " + "A" * 2000
        paragraphs.append(build_paragraph(text, include_page_break=include_break))

    docx_bytes = create_docx(paragraphs)

    target_size_mb = 0.00102
    target_bytes = int(target_size_mb * 1024 * 1024)

    result = split_docx_by_size(docx_bytes, target_size_mb=target_size_mb, original_name="guide.docx")

    assert result.total_pages == 5
    assert len(result.chunks) >= 2

    combined_xml = "".join(extract_document_xml(chunk.data) for chunk in result.chunks)
    for idx in range(5):
        assert f"페이지{idx}" in combined_xml

    for chunk in result.chunks:
        if chunk.start_page != chunk.end_page:
            assert len(chunk.data) <= target_bytes


def test_split_errors_when_document_missing(tmp_path):
    with pytest.raises(DocxSplitError):
        split_docx_by_size(b"not-a-zip", target_size_mb=1, original_name="broken.docx")


def test_split_errors_when_static_overhead_exceeds_target():
    large_font = os.urandom(5 * 1024 * 1024)
    docx_bytes = create_docx(
        [build_paragraph("폰트가 포함된 문서")],
        extra_files={"word/fonts/font1.odttf": large_font},
    )

    with pytest.raises(DocxSplitError) as excinfo:
        split_docx_by_size(docx_bytes, target_size_mb=1, original_name="font.docx")

    message = str(excinfo.value)
    assert "최소 생성 용량" in message


def test_split_errors_when_single_page_is_too_large():
    heavy_image = os.urandom(4 * 1024 * 1024)
    paragraphs = [
        (
            "<w:p>"
            "<w:r><w:t>이미지 페이지</w:t></w:r>"
            "<w:r>"
            "<w:drawing xmlns:wp='http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing' "
            "xmlns:a='http://schemas.openxmlformats.org/drawingml/2006/main' "
            "xmlns:pic='http://schemas.openxmlformats.org/drawingml/2006/picture'>"
            "<wp:inline>"
            "<a:graphic>"
            "<a:graphicData uri='http://schemas.openxmlformats.org/drawingml/2006/picture'>"
            "<pic:pic>"
            "<pic:blipFill><a:blip r:embed='rIdImage1'/></pic:blipFill>"
            "<pic:spPr/>"
            "</pic:pic>"
            "</a:graphicData>"
            "</a:graphic>"
            "</wp:inline>"
            "</w:drawing>"
            "</w:r>"
            "<w:r><w:br w:type='page'/></w:r>"
            "</w:p>"
        ),
        build_paragraph("텍스트 페이지"),
    ]

    rels_xml = """<?xml version='1.0' encoding='UTF-8'?>
    <Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>
      <Relationship Id='rIdImage1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/image' Target='media/image1.png'/>
    </Relationships>
    """

    docx_bytes = create_docx(
        paragraphs,
        extra_files={
            "word/_rels/document.xml.rels": rels_xml.encode("utf-8"),
            "word/media/image1.png": heavy_image,
        },
    )

    with pytest.raises(DocxSplitError) as excinfo:
        split_docx_by_size(docx_bytes, target_size_mb=0.5, original_name="heavy.docx")

    message = str(excinfo.value)
    assert "요청한 분할 용량" in message
    assert "페이지" in message
