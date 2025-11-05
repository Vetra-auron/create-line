from __future__ import annotations

import math
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import List, Sequence
from xml.etree import ElementTree as ET
from copy import deepcopy
import zipfile

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def qn(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


@dataclass
class Chunk:
    filename: str
    data: bytes
    start_page: int
    end_page: int


@dataclass
class SplitResult:
    chunks: List[Chunk]
    total_pages: int
    total_size: int


class DocxSplitError(ValueError):
    """Raised when a DOCX file cannot be split."""


def split_docx_by_size(docx_bytes: bytes, target_size_mb: float, original_name: str) -> SplitResult:
    if not docx_bytes:
        raise ValueError("빈 파일은 처리할 수 없습니다.")

    target_bytes = int(target_size_mb * 1024 * 1024)
    if target_bytes <= 0:
        raise ValueError("분할 기준이 되는 용량(MB)은 0보다 커야 합니다.")

    try:
        with zipfile.ZipFile(BytesIO(docx_bytes)) as docx_zip:
            try:
                document_xml = docx_zip.read("word/document.xml")
            except KeyError as exc:
                raise DocxSplitError("DOCX 문서 구조를 확인할 수 없습니다.") from exc
            template_files = {
                name: docx_zip.read(name)
                for name in docx_zip.namelist()
                if name != "word/document.xml"
            }
    except zipfile.BadZipFile as exc:
        raise DocxSplitError("유효한 DOCX 파일이 아닙니다.") from exc

    tree = ET.fromstring(document_xml)
    body = tree.find(qn("body"))
    if body is None:
        raise DocxSplitError("문서 본문을 읽을 수 없습니다.")

    sect_pr = body.find(qn("sectPr"))
    if sect_pr is not None:
        body.remove(sect_pr)

    body_elements = [deepcopy(child) for child in body]

    pages = _split_body_into_pages(body)
    if not pages:
        pages = [body_elements]

    total_size = len(docx_bytes)
    target_chunks = max(1, math.ceil(total_size / target_bytes))

    if len(pages) < target_chunks:
        pages = _fallback_grouping(body_elements, target_chunks)

    pages_per_chunk = math.ceil(len(pages) / target_chunks)

    base_tree = tree

    base_filename = Path(original_name).stem
    chunks: List[Chunk] = []

    for idx in range(0, len(pages), pages_per_chunk):
        chunk_pages = pages[idx : idx + pages_per_chunk]
        if not chunk_pages:
            continue
        start_page = idx + 1
        end_page = idx + len(chunk_pages)
        elements = [deepcopy(el) for page in chunk_pages for el in page]

        chunk_tree = deepcopy(base_tree)
        chunk_body = chunk_tree.find(qn("body"))
        if chunk_body is None:
            raise DocxSplitError("문서 본문을 생성하지 못했습니다.")
        for child in list(chunk_body):
            chunk_body.remove(child)
        for element in elements:
            chunk_body.append(element)
        if sect_pr is not None:
            chunk_body.append(deepcopy(sect_pr))

        chunk_xml = ET.tostring(chunk_tree, encoding="utf-8", xml_declaration=True)

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in template_files.items():
                archive.writestr(name, data)
            archive.writestr("word/document.xml", chunk_xml)
        buffer.seek(0)

        chunk_filename = f"{base_filename}_{start_page:02d}_{end_page:02d}.docx"
        chunks.append(
            Chunk(
                filename=chunk_filename,
                data=buffer.getvalue(),
                start_page=start_page,
                end_page=end_page,
            )
        )

    return SplitResult(chunks=chunks, total_pages=len(pages), total_size=total_size)


def _fallback_grouping(elements: Sequence[ET.Element], target_chunks: int) -> List[List[ET.Element]]:
    if not elements:
        return [[]]
    chunk_size = max(1, math.ceil(len(elements) / target_chunks))
    grouped: List[List[ET.Element]] = []
    for idx in range(0, len(elements), chunk_size):
        grouped.append([deepcopy(el) for el in elements[idx : idx + chunk_size]])
    return grouped


def _split_body_into_pages(body: ET.Element) -> List[List[ET.Element]]:
    pages: List[List[ET.Element]] = []
    current_page: List[ET.Element] = []

    for child in body:
        if child.tag == qn("p"):
            if _has_page_break_before(child) and current_page:
                pages.append(current_page)
                current_page = []
            segments = _split_paragraph(child)
            for idx, segment in enumerate(segments):
                if segment is not None:
                    current_page.append(segment)
                if idx < len(segments) - 1:
                    pages.append(current_page)
                    current_page = []
        else:
            current_page.append(deepcopy(child))

    if current_page:
        pages.append(current_page)

    return pages


def _has_page_break_before(paragraph: ET.Element) -> bool:
    p_pr = paragraph.find(qn("pPr"))
    if p_pr is None:
        return False
    return p_pr.find(qn("pageBreakBefore")) is not None


def _split_paragraph(paragraph: ET.Element) -> List[ET.Element]:
    segments: List[ET.Element] = []
    current = _create_paragraph_shell(paragraph)
    has_content = False

    for child in paragraph:
        if child.tag == qn("pPr"):
            continue
        child_segments = _split_child(child)
        for idx, (seg_element, has_break) in enumerate(child_segments):
            if seg_element is not None:
                current.append(seg_element)
                has_content = True
            if has_break:
                segments.append(current)
                current = _create_paragraph_shell(paragraph)
                has_content = False

    if has_content or not segments:
        segments.append(current)

    return segments


def _split_child(element: ET.Element) -> List[tuple[ET.Element | None, bool]]:
    if element.tag == qn("r"):
        return _split_run(element)
    return [(deepcopy(element), False)]


def _split_run(run: ET.Element) -> List[tuple[ET.Element | None, bool]]:
    segments: List[tuple[ET.Element | None, bool]] = []
    current = _create_run_shell(run)
    has_content = False

    for child in run:
        if child.tag == qn("rPr"):
            continue
        if _is_page_break_element(child):
            if has_content:
                segments.append((current, True))
            else:
                segments.append((None, True))
            current = _create_run_shell(run)
            has_content = False
            continue
        current.append(deepcopy(child))
        has_content = True

    if has_content:
        segments.append((current, False))
    elif not segments:
        segments.append((None, False))

    return segments


def _create_paragraph_shell(paragraph: ET.Element) -> ET.Element:
    new_para = ET.Element(paragraph.tag, paragraph.attrib)
    p_pr = paragraph.find(qn("pPr"))
    if p_pr is not None:
        new_para.append(deepcopy(p_pr))
    return new_para


def _create_run_shell(run: ET.Element) -> ET.Element:
    new_run = ET.Element(run.tag, run.attrib)
    r_pr = run.find(qn("rPr"))
    if r_pr is not None:
        new_run.append(deepcopy(r_pr))
    return new_run


def _is_page_break_element(element: ET.Element) -> bool:
    if element.tag == qn("lastRenderedPageBreak"):
        return True
    if element.tag == qn("br"):
        if element.get(qn("type")) == "page":
            return True
    return False
