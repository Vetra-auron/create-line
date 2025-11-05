from __future__ import annotations

import posixpath
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set
from xml.etree import ElementTree as ET
from copy import deepcopy
import zipfile

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


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

            try:
                rels_xml = docx_zip.read("word/_rels/document.xml.rels")
                relationships_root = ET.fromstring(rels_xml)
            except KeyError:
                relationships_root = None

            static_files: Dict[str, bytes] = {}
            heavy_files: Dict[str, bytes] = {}
            for name in docx_zip.namelist():
                if name in {"word/document.xml", "word/_rels/document.xml.rels"}:
                    continue
                data = docx_zip.read(name)
                if name.startswith("word/media/") or name.startswith("word/embeddings/") or name.startswith("word/charts/"):
                    heavy_files[name] = data
                else:
                    static_files[name] = data
    except zipfile.BadZipFile as exc:
        raise DocxSplitError("유효한 DOCX 파일이 아닙니다.") from exc

    tree = ET.fromstring(document_xml)
    body = tree.find(qn("body"))
    if body is None:
        raise DocxSplitError("문서 본문을 읽을 수 없습니다.")

    sect_pr = body.find(qn("sectPr"))
    if sect_pr is not None:
        body.remove(sect_pr)

    pages = _split_body_into_pages(body)
    if not pages:
        pages = [[deepcopy(child) for child in body]]

    total_size = len(docx_bytes)
    base_filename = Path(original_name).stem
    chunks: List[Chunk] = []

    template = _DocxTemplate(
        base_tree=tree,
        sect_pr=sect_pr,
        static_files=static_files,
        heavy_files=heavy_files,
        relationships_root=relationships_root,
    )

    minimum_chunk_size = len(template.render([]))
    if minimum_chunk_size > target_bytes:
        minimum_mb = minimum_chunk_size / (1024 * 1024)
        requested_mb = target_bytes / (1024 * 1024)
        raise DocxSplitError(
            "문서에 포함된 필수 리소스(폰트, 스타일 등)의 용량이 크기 때문에 "
            f"요청한 분할 용량({requested_mb:.2f}MB)보다 작은 파일을 만들 수 없습니다. "
            f"최소 생성 용량은 약 {minimum_mb:.2f}MB입니다."
        )

    current_pages: List[List[ET.Element]] = []
    current_start = 1
    cached_bytes: bytes | None = None
    requested_mb = target_bytes / (1024 * 1024)

    def _raise_page_too_large(start: int, end: int, size_bytes: int) -> None:
        chunk_mb = size_bytes / (1024 * 1024)
        if start == end:
            page_label = f"{start}페이지"
        else:
            page_label = f"{start}-{end}페이지 범위"
        raise DocxSplitError(
            f"{page_label}에 포함된 리소스 용량이 커서 요청한 분할 용량({requested_mb:.2f}MB)을 초과합니다. "
            f"해당 범위만 분리해도 최소 약 {chunk_mb:.2f}MB가 필요합니다."
        )

    for page_index, page in enumerate(pages, start=1):
        candidate_pages = current_pages + [page]
        candidate_bytes = template.render(candidate_pages)

        if len(candidate_bytes) > target_bytes:
            if current_pages and len(candidate_pages) > 1:
                start_page = current_start
                end_page = current_start + len(current_pages) - 1
                final_bytes = cached_bytes if cached_bytes is not None else template.render(current_pages)
                if len(final_bytes) > target_bytes:
                    _raise_page_too_large(start_page, end_page, len(final_bytes))
                chunk_filename = f"{base_filename}_{start_page:02d}_{end_page:02d}.docx"
                chunks.append(
                    Chunk(
                        filename=chunk_filename,
                        data=final_bytes,
                        start_page=start_page,
                        end_page=end_page,
                    )
                )
                current_pages = [page]
                current_start = page_index
                candidate_bytes = template.render(current_pages)
                if len(candidate_bytes) > target_bytes:
                    _raise_page_too_large(page_index, page_index, len(candidate_bytes))
            else:
                _raise_page_too_large(page_index, page_index, len(candidate_bytes))
        else:
            current_pages = candidate_pages

        cached_bytes = candidate_bytes

    if current_pages:
        start_page = current_start
        end_page = current_start + len(current_pages) - 1
        final_bytes = cached_bytes if cached_bytes is not None else template.render(current_pages)
        if len(final_bytes) > target_bytes:
            _raise_page_too_large(start_page, end_page, len(final_bytes))
        chunk_filename = f"{base_filename}_{start_page:02d}_{end_page:02d}.docx"
        chunks.append(
            Chunk(
                filename=chunk_filename,
                data=final_bytes,
                start_page=start_page,
                end_page=end_page,
            )
        )

    return SplitResult(chunks=chunks, total_pages=len(pages), total_size=total_size)


def _split_body_into_pages(body: ET.Element) -> List[List[ET.Element]]:
    pages: List[List[ET.Element]] = []
    current_page: List[ET.Element] = []

    for child in body:
        if child.tag == qn("p"):
            if _has_page_break_before(child) and current_page:
                pages.append(current_page)
                current_page = []
            segments = _split_paragraph(child)
            for segment, has_break in segments:
                if segment is not None:
                    current_page.append(segment)
                if has_break:
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


def _split_paragraph(paragraph: ET.Element) -> List[tuple[ET.Element | None, bool]]:
    segments: List[tuple[ET.Element | None, bool]] = []
    current = _create_paragraph_shell(paragraph)
    has_content = False

    for child in paragraph:
        if child.tag == qn("pPr"):
            continue
        child_segments = _split_child(child)
        for seg_element, has_break in child_segments:
            if seg_element is not None:
                current.append(seg_element)
                has_content = True
            if has_break:
                if has_content:
                    segments.append((current, True))
                else:
                    segments.append((None, True))
                current = _create_paragraph_shell(paragraph)
                has_content = False

    if has_content:
        segments.append((current, False))
    elif not segments:
        segments.append((current, False))

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


class _DocxTemplate:
    def __init__(
        self,
        *,
        base_tree: ET.Element,
        sect_pr: ET.Element | None,
        static_files: Dict[str, bytes],
        heavy_files: Dict[str, bytes],
        relationships_root: ET.Element | None,
    ) -> None:
        self._base_tree = base_tree
        self._sect_pr = sect_pr
        self._static_files = static_files
        self._heavy_files = heavy_files
        self._relationships_root = relationships_root
        self._relationships = self._parse_relationships(relationships_root)

    def render(self, pages: Sequence[Sequence[ET.Element]]) -> bytes:
        chunk_tree = deepcopy(self._base_tree)
        chunk_body = chunk_tree.find(qn("body"))
        if chunk_body is None:
            raise DocxSplitError("문서 본문을 생성하지 못했습니다.")

        for child in list(chunk_body):
            chunk_body.remove(child)

        for page in pages:
            for element in page:
                chunk_body.append(deepcopy(element))

        if self._sect_pr is not None:
            chunk_body.append(deepcopy(self._sect_pr))

        chunk_xml = ET.tostring(chunk_tree, encoding="utf-8", xml_declaration=True)

        used_relationships = _collect_relationship_ids(chunk_body)
        rels_xml = self._build_relationships_xml(used_relationships)

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in self._static_files.items():
                archive.writestr(name, data)

            for name in self._select_heavy_files(used_relationships):
                archive.writestr(name, self._heavy_files[name])

            archive.writestr("word/document.xml", chunk_xml)
            if rels_xml is not None:
                archive.writestr("word/_rels/document.xml.rels", rels_xml)

        buffer.seek(0)
        return buffer.getvalue()

    def _build_relationships_xml(self, used_relationships: Set[str]) -> bytes | None:
        if self._relationships_root is None:
            return None

        relationships_root = deepcopy(self._relationships_root)
        for rel in list(relationships_root):
            rel_id = rel.get("Id")
            target = rel.get("Target", "")
            if rel_id is None:
                continue
            if _is_size_heavy_target(target) and rel_id not in used_relationships:
                relationships_root.remove(rel)

        return ET.tostring(relationships_root, encoding="utf-8", xml_declaration=True)

    def _select_heavy_files(self, used_relationships: Set[str]) -> Iterable[str]:
        if not self._heavy_files:
            return []

        selected: Set[str] = set()
        for rel_id in used_relationships:
            target = self._relationships.get(rel_id)
            if not target:
                continue
            path = _resolve_relationship_target(target)
            if path in self._heavy_files:
                selected.add(path)
        return sorted(selected)

    @staticmethod
    def _parse_relationships(root: ET.Element | None) -> Dict[str, str]:
        if root is None:
            return {}

        relationships: Dict[str, str] = {}
        for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
            rel_id = rel.get("Id")
            target = rel.get("Target")
            if rel_id and target:
                relationships[rel_id] = target
        return relationships


def _collect_relationship_ids(element: ET.Element) -> Set[str]:
    relationship_ids: Set[str] = set()
    stack = [element]
    while stack:
        current = stack.pop()
        for attrib_name, attrib_value in current.attrib.items():
            if attrib_name.startswith(f"{{{R_NS}}}") and attrib_value:
                relationship_ids.add(attrib_value)
        stack.extend(list(current))
    return relationship_ids


def _resolve_relationship_target(target: str) -> str:
    normalized = posixpath.normpath(posixpath.join("word", target))
    return normalized


def _is_size_heavy_target(target: str) -> bool:
    lowered = target.lower()
    heavy_prefixes = (
        "media/",
        "../media/",
        "embeddings/",
        "../embeddings/",
        "charts/",
        "../charts/",
    )
    return lowered.startswith(heavy_prefixes)
