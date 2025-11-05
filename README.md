# DOCX 페이지 분할 웹앱

업로드한 DOCX 문서를 지정한 용량 단위로 나누어 다운로드할 수 있는 Flask 기반 웹 애플리케이션입니다. 문서 내부에 페이지 구분 정보(`w:lastRenderedPageBreak`, `w:br type="page"`, `pageBreakBefore`)가 있으면 해당 정보를 우선적으로 활용하여 페이지 단위로 나누고, 구분 정보가 없는 경우에는 문단 단위로 균등하게 분리합니다.

## 주요 기능
- DOCX 파일 업로드 및 목표 용량(MB) 지정
- 문서 구조 분석 후 페이지/문단 단위 분할
- 리소스 처리 옵션(원본 유지, 이미지 압축, 리소스 제거) 제공
- 분할된 DOCX 파일을 페이지 범위가 포함된 이름으로 ZIP 압축하여 제공

### 리소스 처리 옵션
- **원본 유지**: 이미지·차트·임베드 파일을 변환하지 않고 그대로 포함합니다.
- **이미지 압축**: PNG 이미지를 지정한 최대 해상도로 축소해 용량을 줄입니다. 기본값은 1600px, 품질 70이며, 화면에서 값을 조정할 수 있습니다.
- (JPEG 및 기타 형식은 현재 원본 품질을 유지하며 추후 확장을 위해 품질 값 입력란을 유지합니다.)
- **리소스 제거**: 이미지·차트·임베드 리소스를 본문에서 제거하고 텍스트 및 필수 구조만 남겨 최소 용량으로 분할합니다.

## 로컬 실행 방법
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

애플리케이션은 기본적으로 `http://127.0.0.1:5000/`에서 실행됩니다.

## 테스트 실행 방법
애플리케이션의 DOCX 분할 로직은 `pytest` 기반 단위 테스트로 검증할 수 있습니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```
