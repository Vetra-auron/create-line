import io
import zipfile
from pathlib import Path

from flask import (Blueprint, Response, flash, redirect, render_template,
                   request, send_file, url_for)
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .splitter import split_docx_by_size

bp = Blueprint("main", __name__)


def _validate_file(file: FileStorage) -> str:
    filename = secure_filename(file.filename or "")
    if not filename:
        raise ValueError("업로드된 파일 이름을 확인할 수 없습니다.")
    if not filename.lower().endswith(".docx"):
        raise ValueError("DOCX 파일만 업로드할 수 있습니다.")
    return filename


@bp.route("/", methods=["GET", "POST"])
def index() -> Response:
    if request.method == "POST":
        file = request.files.get("docx_file")
        target_size_raw = request.form.get("target_size")

        if not file or file.filename == "":
            flash("분할할 DOCX 파일을 선택해주세요.")
            return redirect(url_for("main.index"))

        resource_strategy = request.form.get("resource_strategy", "keep")
        image_max_dimension_raw = request.form.get("image_max_dimension", "").strip()
        jpeg_quality_raw = request.form.get("jpeg_quality", "").strip()

        try:
            filename = _validate_file(file)
            target_size = float(target_size_raw) if target_size_raw else 0.0
            if target_size <= 0:
                raise ValueError("분할 기준이 되는 파일 용량(MB)을 0보다 큰 값으로 입력해주세요.")

            image_max_dimension = 1600
            jpeg_quality = 70
            if resource_strategy == "compress":
                if image_max_dimension_raw:
                    image_max_dimension = int(image_max_dimension_raw)
                if jpeg_quality_raw:
                    jpeg_quality = int(jpeg_quality_raw)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("main.index"))

        temp_bytes = io.BytesIO()
        file.save(temp_bytes)
        docx_bytes = temp_bytes.getvalue()

        try:
            result = split_docx_by_size(
                docx_bytes,
                target_size,
                filename,
                resource_strategy=resource_strategy,
                image_max_dimension=image_max_dimension,
                jpeg_quality=jpeg_quality,
            )
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("main.index"))
        except Exception as exc:  # pragma: no cover - unexpected errors
            flash(f"파일을 분할하는 도중 오류가 발생했습니다: {exc}")
            return redirect(url_for("main.index"))

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for chunk in result.chunks:
                archive.writestr(chunk.filename, chunk.data)

        zip_buffer.seek(0)
        download_name = f"{Path(filename).stem}_split.zip"
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/zip",
        )

    return render_template("index.html")
