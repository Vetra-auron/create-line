# 견적서 생성 애플리케이션

Python과 Tkinter를 사용하여 견적서(PC 앱)를 작성하고 PDF로 저장하거나 인쇄할 수 있는 데스크톱 애플리케이션입니다.

## 기능 개요

- 업체명, 날짜, 품명, Model No., 수량, 단위, 단가, 금액 입력
- 다중 품목을 추가/삭제하고 합계 자동 계산
- 원인·수리 내역을 선택(드롭다운) 또는 직접 입력
- 입력한 내용을 PDF 문서로 저장
- 생성된 PDF를 기본 프린터로 인쇄

## 사전 준비

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## 실행 방법

```bash
python -m app.main
```

또는 가상 환경을 활성화한 상태에서 다음과 같이 직접 실행할 수도 있습니다.

```bash
python app/main.py
```

## PDF 생성 및 인쇄

1. 기본 정보와 품목, 원인·수리 정보를 입력합니다.
2. **PDF 저장** 버튼을 클릭하여 파일 위치를 지정합니다.
3. **PDF 인쇄** 버튼을 누르면 임시 PDF를 만들어 기본 프린터로 전송합니다.

## 테스트

애플리케이션 모듈이 정상 로드되는지 컴파일 검사를 수행할 수 있습니다.

```bash
python -m compileall app
```
