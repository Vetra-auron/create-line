# create-line

간단한 일정 관리 앱입니다. `schedule_app.py`를 통해 일정을 추가하거나 조회할 수 있습니다.

Python 3가 설치되어 있어야 합니다. 터미널에서 다음 명령을 실행합니다:

```
python schedule_app.py [명령] [옵션]
```

### 명령 종류

- `add <내용>`: 새 일정을 추가합니다.
- `list`: 저장된 일정을 목록으로 확인합니다.
- `remove <번호>`: 번호에 해당하는 일정을 삭제합니다.
- `clear`: 모든 일정을 삭제합니다.

### 사용 예시

```
python schedule_app.py add "회의 준비"
python schedule_app.py list
python schedule_app.py remove 1
python schedule_app.py clear
```
