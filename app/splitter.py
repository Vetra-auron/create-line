from __future__ import annotations

import posixpath
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set
from xml.etree import ElementTree as ET
from copy import deepcopy
import struct
import zipfile
import zlib

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


def split_docx_by_size(
    docx_bytes: bytes,
    target_size_mb: float,
    original_name: str,
    *,
    resource_strategy: str = "keep",
    image_max_dimension: int = 1600,
    jpeg_quality: int = 70,
) -> SplitResult:
    if not docx_bytes:
        raise ValueError("빈 파일은 처리할 수 없습니다.")

    target_bytes = int(target_size_mb * 1024 * 1024)
    if target_bytes <= 0:
        raise ValueError("분할 기준이 되는 용량(MB)은 0보다 커야 합니다.")

    normalized_strategy = resource_strategy.lower()
    if normalized_strategy not in {"keep", "compress", "strip"}:
        raise ValueError("지원하지 않는 리소스 처리 옵션입니다.")

    if normalized_strategy == "compress":
        if image_max_dimension <= 0:
            raise ValueError("이미지 최대 해상도는 0보다 커야 합니다.")
        if not 1 <= jpeg_quality <= 95:
            raise ValueError("JPEG 품질은 1에서 95 사이의 값으로 지정해주세요.")

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
        resource_strategy=normalized_strategy,
        image_max_dimension=image_max_dimension,
        jpeg_quality=jpeg_quality,
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

    requested_mb = target_bytes / (1024 * 1024)
    total_pages = len(pages)
    pad_width = max(2, len(str(total_pages)))

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

    page_index = 0
    while page_index < total_pages:
        remaining_pages = total_pages - page_index
        low = 1
        high = remaining_pages
        best_count = 0
        best_bytes: bytes | None = None
        last_overflow_bytes: bytes | None = None

        while low <= high:
            mid = (low + high) // 2
            candidate_pages = pages[page_index : page_index + mid]
            candidate_bytes = template.render(candidate_pages)
            if len(candidate_bytes) <= target_bytes:
                best_count = mid
                best_bytes = candidate_bytes
                low = mid + 1
            else:
                last_overflow_bytes = candidate_bytes
                high = mid - 1

        if best_count == 0:
            overflow_bytes = last_overflow_bytes
            if overflow_bytes is None:
                overflow_bytes = template.render(pages[page_index : page_index + 1])
            _raise_page_too_large(page_index + 1, page_index + 1, len(overflow_bytes))

        start_page = page_index + 1
        end_page = page_index + best_count
        if best_bytes is None:  # pragma: no cover - defensive guard
            raise DocxSplitError("분할 결과를 생성하지 못했습니다.")

        chunk_filename = f"{base_filename}_{start_page:0{pad_width}d}_{end_page:0{pad_width}d}.docx"
        chunks.append(
            Chunk(
                filename=chunk_filename,
                data=best_bytes,
                start_page=start_page,
                end_page=end_page,
            )
        )
        page_index += best_count

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
        resource_strategy: str,
        image_max_dimension: int,
        jpeg_quality: int,
    ) -> None:
        self._base_tree = base_tree
        self._sect_pr = sect_pr
        self._static_files = static_files
        self._heavy_files = heavy_files
        self._relationships_root = relationships_root
        self._relationships = self._parse_relationships(relationships_root)
        self._resource_strategy = resource_strategy
        self._image_max_dimension = image_max_dimension
        self._jpeg_quality = jpeg_quality
        self._heavy_relationship_ids: Set[str] = {
            rel_id
            for rel_id, target in self._relationships.items()
            if _is_size_heavy_target(target)
        }
        self._heavy_cache: Dict[str, bytes] = {}

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

        removed_heavy_relationships: Set[str] = set()
        if self._resource_strategy == "strip" and self._heavy_relationship_ids:
            removed_heavy_relationships = self._strip_heavy_relationships(chunk_body)

        chunk_xml = ET.tostring(chunk_tree, encoding="utf-8", xml_declaration=True)

        used_relationships = _collect_relationship_ids(chunk_body)
        if removed_heavy_relationships:
            used_relationships -= removed_heavy_relationships
        rels_xml = self._build_relationships_xml(used_relationships)

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in self._static_files.items():
                archive.writestr(name, data)

            for name in self._select_heavy_files(used_relationships):
                heavy_bytes = self._get_heavy_file_bytes(name)
                if heavy_bytes is not None:
                    archive.writestr(name, heavy_bytes)

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

    def _strip_heavy_relationships(self, parent: ET.Element) -> Set[str]:
        removed: Set[str] = set()
        for child in list(parent):
            removed |= self._strip_heavy_relationships(child)
            referenced = _collect_specific_relationship_ids(child, self._heavy_relationship_ids)
            if referenced:
                parent.remove(child)
                removed |= referenced
        return removed

    def _get_heavy_file_bytes(self, name: str) -> bytes | None:
        if self._resource_strategy == "strip":
            return None

        if self._resource_strategy != "compress":
            return self._heavy_files[name]

        if name in self._heavy_cache:
            return self._heavy_cache[name]

        original = self._heavy_files[name]
        processed = self._compress_heavy_file(name, original)
        self._heavy_cache[name] = processed
        return processed

    def _compress_heavy_file(self, name: str, data: bytes) -> bytes:
        lowered = name.lower()
        if lowered.endswith(".png"):
            compressed = _downscale_png_bytes(data, self._image_max_dimension)
            if compressed is not None and len(compressed) < len(data):
                return compressed
        return data

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


def _collect_specific_relationship_ids(element: ET.Element, targets: Set[str]) -> Set[str]:
    if not targets:
        return set()

    matched: Set[str] = set()
    for attrib_name, attrib_value in element.attrib.items():
        if attrib_name.startswith(f"{{{R_NS}}}") and attrib_value in targets:
            matched.add(attrib_value)

    for child in element:
        matched |= _collect_specific_relationship_ids(child, targets)

    return matched


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


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _downscale_png_bytes(data: bytes, max_dimension: int) -> bytes | None:
    if max_dimension <= 0:
        return None

    try:
        width, height, bit_depth, color_type, rows = _parse_png(data)
    except ValueError:
        return None

    if max(width, height) <= max_dimension:
        return None

    new_width, new_height, new_rows = _resize_png_rows(rows, width, height, color_type, max_dimension)
    return _encode_png(new_width, new_height, bit_depth, color_type, new_rows)


def _parse_png(data: bytes) -> tuple[int, int, int, int, List[List[int]]]:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("PNG 시그니처가 올바르지 않습니다.")

    stream = memoryview(data)
    pos = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = None
    idat_parts: List[bytes] = []

    while pos + 8 <= len(stream):
        length = struct.unpack(">I", stream[pos : pos + 4])[0]
        pos += 4
        chunk_type = bytes(stream[pos : pos + 4])
        pos += 4
        chunk_data = bytes(stream[pos : pos + length])
        pos += length
        pos += 4  # skip CRC

        if chunk_type == b"IHDR":
            if length != 13:
                raise ValueError("IHDR 길이가 올바르지 않습니다.")
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            if bit_depth != 8 or compression != 0 or filter_method != 0 or interlace != 0:
                raise ValueError("지원하지 않는 PNG 압축 형식입니다.")
            if color_type not in (2, 6):
                raise ValueError("RGB 혹은 RGBA PNG만 지원합니다.")
        elif chunk_type == b"IDAT":
            idat_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if not idat_parts or width is None or height is None or bit_depth is None or color_type is None:
        raise ValueError("PNG 데이터를 해석할 수 없습니다.")

    decompressed = zlib.decompress(b"".join(idat_parts))
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    expected = (stride + 1) * height
    if len(decompressed) != expected:
        raise ValueError("PNG 데이터 길이가 예상과 다릅니다.")

    rows: List[List[int]] = []
    prev_row = [0] * stride
    offset = 0
    for _ in range(height):
        filter_type = decompressed[offset]
        offset += 1
        row_bytes = list(decompressed[offset : offset + stride])
        offset += stride
        row = _apply_png_filter(filter_type, row_bytes, prev_row, channels)
        rows.append(row)
        prev_row = row

    return width, height, bit_depth, color_type, rows


def _apply_png_filter(filter_type: int, raw_row: List[int], prev_row: List[int], channels: int) -> List[int]:
    if filter_type == 0:
        return raw_row

    row = [0] * len(raw_row)
    if filter_type == 1:
        for idx, value in enumerate(raw_row):
            left = row[idx - channels] if idx >= channels else 0
            row[idx] = (value + left) & 0xFF
    elif filter_type == 2:
        for idx, value in enumerate(raw_row):
            up = prev_row[idx]
            row[idx] = (value + up) & 0xFF
    elif filter_type == 3:
        for idx, value in enumerate(raw_row):
            left = row[idx - channels] if idx >= channels else 0
            up = prev_row[idx]
            row[idx] = (value + ((left + up) // 2)) & 0xFF
    elif filter_type == 4:
        for idx, value in enumerate(raw_row):
            left = row[idx - channels] if idx >= channels else 0
            up = prev_row[idx]
            up_left = prev_row[idx - channels] if idx >= channels else 0
            row[idx] = (value + _paeth_predictor(left, up, up_left)) & 0xFF
    else:  # pragma: no cover - unexpected filter type
        raise ValueError("지원하지 않는 PNG 필터 유형입니다.")
    return row


def _encode_png(width: int, height: int, bit_depth: int, color_type: int, rows: List[List[int]]) -> bytes:
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    raw = bytearray()
    for row in rows:
        if len(row) != stride:
            raise ValueError("PNG 행 길이가 일치하지 않습니다.")
        raw.append(0)
        raw.extend(row)

    compressed = zlib.compress(bytes(raw), level=9)
    parts = [PNG_SIGNATURE]
    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    parts.append(_png_chunk(b"IHDR", ihdr))
    parts.append(_png_chunk(b"IDAT", compressed))
    parts.append(_png_chunk(b"IEND", b""))
    return b"".join(parts)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc


def _resize_png_rows(
    rows: List[List[int]],
    width: int,
    height: int,
    color_type: int,
    max_dimension: int,
) -> tuple[int, int, List[List[int]]]:
    channels = 4 if color_type == 6 else 3
    ratio = max(width, height) / max_dimension
    new_width = max(1, int(width / ratio))
    new_height = max(1, int(height / ratio))
    x_scale = width / new_width
    y_scale = height / new_height

    resized: List[List[int]] = []
    for new_y in range(new_height):
        src_y = min(height - 1, int(new_y * y_scale))
        src_row = rows[src_y]
        new_row: List[int] = []
        for new_x in range(new_width):
            src_x = min(width - 1, int(new_x * x_scale))
            start = src_x * channels
            new_row.extend(src_row[start : start + channels])
        resized.append(new_row)

    return new_width, new_height, resized


def _paeth_predictor(left: int, up: int, up_left: int) -> int:
    # Implementation based on PNG specification.
    p = left + up - up_left
    pa = abs(p - left)
    pb = abs(p - up)
    pc = abs(p - up_left)
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return up
    return up_left
