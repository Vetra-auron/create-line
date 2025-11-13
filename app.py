"""거래처 정보를 엑셀 파일에서 불러와 검색 및 메모를 관리하는 데스크톱 앱."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


DISPLAY_PRIORITY_COLUMNS = [
    "거래처명",
    "업체명",
    "거래처",
    "회사명",
    "상호명",
    "고객명",
    "대표자명",
]


class TradingPartnerApp:
    def __init__(self, root: tk.Tk, initial_file: Optional[Path] = None) -> None:
        self.root = root
        self.root.title("거래처 정보 검색")
        self.root.geometry("900x600")

        self.dataframe: Optional[pd.DataFrame] = None
        self.filtered_indices: List[int] = []
        self.current_record_key: Optional[str] = None
        self.notes_path = Path("notes.json")
        self.notes: Dict[str, str] = self._load_notes()

        self._build_ui()

        if initial_file:
            self._load_excel(initial_file)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        file_frame = ttk.Frame(container)
        file_frame.pack(fill=tk.X)

        ttk.Button(file_frame, text="엑셀 불러오기", command=self._prompt_excel).pack(side=tk.LEFT)
        self.file_label_var = tk.StringVar(value="불러온 파일 없음")
        ttk.Label(file_frame, textvariable=self.file_label_var).pack(side=tk.LEFT, padx=10)

        search_frame = ttk.LabelFrame(container, text="검색")
        search_frame.pack(fill=tk.X, pady=10)

        ttk.Label(search_frame, text="대표자명 또는 거래처명:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        search_entry.bind("<Return>", lambda event: self._perform_search())
        ttk.Button(search_frame, text="검색", command=self._perform_search).pack(side=tk.LEFT)

        content_frame = ttk.Frame(container)
        content_frame.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.LabelFrame(content_frame, text="검색 결과")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.result_list = tk.Listbox(list_frame, height=15)
        self.result_list.pack(fill=tk.BOTH, expand=True)
        self.result_list.bind("<<ListboxSelect>>", lambda event: self._on_select())

        detail_frame = ttk.LabelFrame(content_frame, text="거래처 정보")
        detail_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        self.detail_text = tk.Text(detail_frame, wrap=tk.WORD, state=tk.DISABLED, height=15)
        self.detail_text.pack(fill=tk.BOTH, expand=True)

        note_frame = ttk.LabelFrame(container, text="특이사항")
        note_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.note_text = tk.Text(note_frame, height=6)
        self.note_text.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="특이사항 저장", command=self._save_note).pack(side=tk.RIGHT)

    def _prompt_excel(self) -> None:
        file_path = filedialog.askopenfilename(
            title="거래처 엑셀 파일 선택",
            filetypes=[("Excel 파일", "*.xlsx *.xls")],
        )
        if not file_path:
            return
        self._load_excel(Path(file_path))

    def _load_excel(self, file_path: Path) -> None:
        try:
            df = pd.read_excel(file_path)
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("엑셀 오류", f"엑셀 파일을 불러오는 중 문제가 발생했습니다:\n{exc}")
            return

        if df.empty:
            messagebox.showwarning("데이터 없음", "엑셀 파일에 데이터가 없습니다.")
            return

        self.dataframe = df
        self.file_label_var.set(str(file_path))
        self.search_var.set("")
        self._populate_results(df.index.tolist())
        messagebox.showinfo("불러오기 완료", "엑셀 데이터를 성공적으로 불러왔습니다.")

    def _perform_search(self) -> None:
        if self.dataframe is None:
            messagebox.showwarning("데이터 없음", "먼저 엑셀 파일을 불러와 주세요.")
            return

        query = self.search_var.get().strip()
        if not query:
            self._populate_results(self.dataframe.index.tolist())
            return

        query_lower = query.lower()
        matches: List[int] = []

        for idx, row in self.dataframe.iterrows():
            for column in self._searchable_columns(row):
                value = row[column]
                if pd.isna(value):
                    continue
                if query_lower in str(value).lower():
                    matches.append(idx)
                    break

        if not matches:
            messagebox.showinfo("검색 결과 없음", "일치하는 결과가 없습니다.")

        self._populate_results(matches)

    def _searchable_columns(self, row: pd.Series) -> List[str]:
        candidate_columns = [
            col for col in row.index if pd.api.types.is_string_dtype(self.dataframe[col])
        ]
        preferred = [col for col in DISPLAY_PRIORITY_COLUMNS if col in row.index]
        return list(dict.fromkeys(preferred + candidate_columns))

    def _populate_results(self, indices: List[int]) -> None:
        self.filtered_indices = indices
        self.result_list.delete(0, tk.END)

        if self.dataframe is None:
            return

        for idx in indices:
            row = self.dataframe.loc[idx]
            display_text = self._format_display(row)
            self.result_list.insert(tk.END, display_text)

        if indices:
            self.result_list.selection_set(0)
            self._on_select()
        else:
            self._clear_detail()

    def _format_display(self, row: pd.Series) -> str:
        for column in DISPLAY_PRIORITY_COLUMNS:
            if column in row.index and pd.notna(row[column]):
                primary = str(row[column])
                break
        else:
            primary = str(row.iloc[0])

        representative = None
        for candidate in ["대표자명", "대표자", "대표"]:
            if candidate in row.index and pd.notna(row[candidate]):
                representative = str(row[candidate])
                break

        if representative:
            return f"{primary} | 대표: {representative}"
        return primary

    def _on_select(self) -> None:
        if not self.filtered_indices:
            return
        selection = self.result_list.curselection()
        if not selection:
            return
        index = selection[0]
        row_index = self.filtered_indices[index]
        self._show_detail(row_index)

    def _show_detail(self, row_index: int) -> None:
        if self.dataframe is None:
            return
        row = self.dataframe.loc[row_index]

        details = "\n".join(f"{col}: {row[col]}" for col in row.index)
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, details)
        self.detail_text.config(state=tk.DISABLED)

        record_key = self._build_record_key(row_index, row)
        self.current_record_key = record_key
        existing_note = self.notes.get(record_key, "")
        self.note_text.delete("1.0", tk.END)
        self.note_text.insert(tk.END, existing_note)

    def _clear_detail(self) -> None:
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.config(state=tk.DISABLED)
        self.note_text.delete("1.0", tk.END)
        self.current_record_key = None

    def _build_record_key(self, row_index: int, row: pd.Series) -> str:
        key_candidates = [
            "거래처코드",
            "사업자번호",
            "사업자등록번호",
            "고유번호",
        ]
        for column in key_candidates:
            if column in row.index and pd.notna(row[column]):
                return f"{column}:{row[column]}"
        primary = self._format_display(row)
        return f"IDX:{row_index}:{primary}"

    def _save_note(self) -> None:
        if self.current_record_key is None:
            messagebox.showwarning("선택 필요", "특이사항을 저장할 거래처를 먼저 선택하세요.")
            return

        note = self.note_text.get("1.0", tk.END).strip()
        if note:
            self.notes[self.current_record_key] = note
        else:
            self.notes.pop(self.current_record_key, None)

        self._write_notes()
        messagebox.showinfo("저장 완료", "특이사항이 저장되었습니다.")

    def _load_notes(self) -> Dict[str, str]:
        if not self.notes_path.exists():
            return {}
        try:
            return json.loads(self.notes_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            messagebox.showwarning("메모 불러오기", "특이사항 파일을 불러올 수 없어 새로 생성합니다.")
            return {}

    def _write_notes(self) -> None:
        self.notes_path.write_text(json.dumps(self.notes, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    root = tk.Tk()
    initial_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    app = TradingPartnerApp(root, initial_file=initial_file if initial_file and initial_file.exists() else None)
    if initial_file and not initial_file.exists():
        messagebox.showwarning("파일 없음", f"초기 엑셀 파일을 찾을 수 없습니다: {initial_file}")
    root.mainloop()


if __name__ == "__main__":
    main()
