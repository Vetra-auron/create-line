"""Tkinter 기반 견적서 작성 애플리케이션."""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import List

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .models import (
    DEFAULT_CAUSES,
    DEFAULT_REPAIRS,
    QuoteDocument,
    QuoteItem,
)
from .pdf_generator import default_filename, generate_pdf, print_pdf


class QuoteApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("견적서 생성기")
        self.root.geometry("1000x700")

        self.company_var = tk.StringVar()
        self.date_var = tk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))

        self.item_name_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.quantity_var = tk.StringVar()
        self.unit_var = tk.StringVar(value="Set")
        self.unit_price_var = tk.StringVar()
        self.amount_var = tk.StringVar()

        self.cause_choice_var = tk.StringVar()
        self.repair_choice_var = tk.StringVar()

        self.items: List[QuoteItem] = []

        self._build_ui()

    # UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._build_company_frame(main_frame)
        self._build_items_frame(main_frame)
        self._build_cause_repair_frame(main_frame)
        self._build_action_buttons(main_frame)

    def _build_company_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="기본 정보", padding=12)
        frame.pack(fill=tk.X, pady=8)

        ttk.Label(frame, text="업체명").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(frame, textvariable=self.company_var, width=40).grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)

        ttk.Label(frame, text="날짜").grid(row=0, column=2, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(frame, textvariable=self.date_var, width=20).grid(row=0, column=3, sticky=tk.W, padx=4, pady=4)

    def _build_items_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="품목 정보", padding=12)
        frame.pack(fill=tk.BOTH, expand=True, pady=8)

        form_frame = ttk.Frame(frame)
        form_frame.pack(fill=tk.X, pady=(0, 12))

        labels = ["품명", "Model No.", "수량", "단위", "단가", "금액"]
        variables = [
            self.item_name_var,
            self.model_var,
            self.quantity_var,
            self.unit_var,
            self.unit_price_var,
            self.amount_var,
        ]
        widths = [30, 20, 8, 10, 12, 12]

        for idx, (label, var, width) in enumerate(zip(labels, variables, widths)):
            ttk.Label(form_frame, text=label).grid(row=0, column=idx, sticky=tk.W, padx=4, pady=4)
            if label == "단위":
                ttk.Combobox(
                    form_frame,
                    textvariable=self.unit_var,
                    values=["Set", "Pair"],
                    state="readonly",
                    width=width,
                ).grid(row=1, column=idx, sticky=tk.W, padx=4, pady=4)
            elif label == "금액":
                ttk.Entry(form_frame, textvariable=var, width=width, state="readonly").grid(
                    row=1, column=idx, sticky=tk.W, padx=4, pady=4
                )
            else:
                ttk.Entry(form_frame, textvariable=var, width=width).grid(
                    row=1, column=idx, sticky=tk.W, padx=4, pady=4
                )

        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=1, column=len(labels), padx=8)

        ttk.Button(button_frame, text="추가", command=self.add_item).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="선택 삭제", command=self.remove_selected_item).pack(fill=tk.X, pady=2)

        columns = ("name", "model", "qty", "unit", "unit_price", "amount")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True)

        headings = {
            "name": "품명",
            "model": "Model No.",
            "qty": "수량",
            "unit": "단위",
            "unit_price": "단가",
            "amount": "금액",
        }

        style = ttk.Style(self.root)
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"))

        self._tree_width_ratios = {
            "name": 0.28,
            "model": 0.21,
            "qty": 0.12,
            "unit": 0.12,
            "unit_price": 0.13,
            "amount": 0.14,
        }

        default_widths = {
            "name": 200,
            "model": 150,
            "qty": 80,
            "unit": 80,
            "unit_price": 120,
            "amount": 120,
        }

        for key in columns:
            self.tree.heading(key, text=headings[key])
            anchor = tk.CENTER if key in {"qty", "unit"} else tk.W
            if key in {"unit_price", "amount"}:
                anchor = tk.E
            self.tree.column(key, width=default_widths[key], anchor=anchor, stretch=True)

        self.tree.bind("<Configure>", self._resize_tree_columns)

        self.total_var = tk.StringVar(value="0")
        total_frame = ttk.Frame(frame)
        total_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(total_frame, text="합계:", font=("Helvetica", 12, "bold")).pack(side=tk.RIGHT)
        ttk.Label(total_frame, textvariable=self.total_var, font=("Helvetica", 12, "bold")).pack(side=tk.RIGHT, padx=(0, 20))

        self.quantity_var.trace_add("write", lambda *_: self._update_amount_field())
        self.unit_price_var.trace_add("write", lambda *_: self._update_amount_field())

    def _build_cause_repair_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="원인 및 수리 내역", padding=12)
        frame.pack(fill=tk.BOTH, expand=True, pady=8)

        cause_frame = ttk.Frame(frame)
        cause_frame.pack(fill=tk.BOTH, expand=True, pady=4)
        ttk.Label(cause_frame, text="원인 선택").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(cause_frame, textvariable=self.cause_choice_var, values=DEFAULT_CAUSES, state="readonly").grid(
            row=0, column=1, sticky=tk.W, padx=6
        )
        ttk.Label(cause_frame, text="원인 직접 입력").grid(row=1, column=0, sticky=tk.NW, pady=4)
        self.cause_text = tk.Text(cause_frame, height=4)
        self.cause_text.grid(row=1, column=1, sticky=tk.EW, padx=6, pady=4)

        repair_frame = ttk.Frame(frame)
        repair_frame.pack(fill=tk.BOTH, expand=True, pady=4)
        ttk.Label(repair_frame, text="수리 선택").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(repair_frame, textvariable=self.repair_choice_var, values=DEFAULT_REPAIRS, state="readonly").grid(
            row=0, column=1, sticky=tk.W, padx=6
        )
        ttk.Label(repair_frame, text="수리 직접 입력").grid(row=1, column=0, sticky=tk.NW, pady=4)
        self.repair_text = tk.Text(repair_frame, height=4)
        self.repair_text.grid(row=1, column=1, sticky=tk.EW, padx=6, pady=4)

        for frame_widget in (cause_frame, repair_frame):
            frame_widget.columnconfigure(1, weight=1)

    def _build_action_buttons(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=12)

        ttk.Button(frame, text="PDF 저장", command=self.save_pdf).pack(side=tk.RIGHT, padx=4)
        ttk.Button(frame, text="PDF 인쇄", command=self.print_document).pack(side=tk.RIGHT, padx=4)
        ttk.Button(frame, text="초기화", command=self.reset_form).pack(side=tk.LEFT, padx=4)

    # Item management -------------------------------------------------
    def add_item(self) -> None:
        try:
            quantity = int(self.quantity_var.get())
        except ValueError:
            messagebox.showerror("입력 오류", "수량은 정수로 입력해주세요.")
            return

        try:
            unit_price = float(self.unit_price_var.get().replace(",", ""))
        except ValueError:
            messagebox.showerror("입력 오류", "단가는 숫자로 입력해주세요.")
            return

        amount = unit_price * quantity

        unit_value = self.unit_var.get().strip()
        if not unit_value:
            messagebox.showerror("입력 오류", "단위를 선택해주세요.")
            return

        item = QuoteItem(
            name=self.item_name_var.get().strip(),
            model_no=self.model_var.get().strip(),
            quantity=quantity,
            unit=unit_value,
            unit_price=unit_price,
            amount=amount,
        )

        if not item.name:
            messagebox.showerror("입력 오류", "품명을 입력해주세요.")
            return

        self.items.append(item)
        self._refresh_items_tree()
        self._clear_item_inputs()

    def remove_selected_item(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("선택 없음", "삭제할 항목을 선택해주세요.")
            return

        index = self.tree.index(selected[0])
        try:
            del self.items[index]
        except IndexError:
            pass
        self._refresh_items_tree()

    def _refresh_items_tree(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)

        for item in self.items:
            self.tree.insert("", tk.END, values=item.to_row())

        self.total_var.set(f"{sum(item.amount for item in self.items):,.0f} 원")

    def _resize_tree_columns(self, event: tk.Event) -> None:
        if not hasattr(self, "_tree_width_ratios"):
            return

        total_width = max(event.width, 1)
        for key, ratio in self._tree_width_ratios.items():
            width = int(total_width * ratio)
            if width > 0:
                self.tree.column(key, width=width)

    def _update_amount_field(self) -> None:
        quantity_text = self.quantity_var.get().strip()
        unit_price_text = self.unit_price_var.get().strip().replace(",", "")

        try:
            quantity = int(quantity_text)
            unit_price = float(unit_price_text)
        except ValueError:
            self.amount_var.set("")
            return

        amount = quantity * unit_price
        self.amount_var.set(f"{amount:,.0f}")

    def _clear_item_inputs(self) -> None:
        for var in [
            self.item_name_var,
            self.model_var,
            self.quantity_var,
            self.unit_price_var,
        ]:
            var.set("")
        self.unit_var.set("Set")
        self.amount_var.set("")

    # Document handling -----------------------------------------------
    def _collect_document(self) -> QuoteDocument:
        company = self.company_var.get().strip()
        if not company:
            raise ValueError("업체명을 입력해주세요.")

        try:
            quotation_date = datetime.strptime(self.date_var.get().strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("날짜는 YYYY-MM-DD 형식으로 입력해주세요.") from exc

        if not self.items:
            raise ValueError("최소 1개 이상의 품목을 추가해주세요.")

        cause = self._combine_selection_and_text(self.cause_choice_var.get(), self.cause_text.get("1.0", tk.END))
        repair = self._combine_selection_and_text(self.repair_choice_var.get(), self.repair_text.get("1.0", tk.END))

        return QuoteDocument(
            company_name=company,
            quotation_date=quotation_date,
            items=list(self.items),
            cause=cause,
            repair_detail=repair,
        )

    @staticmethod
    def _combine_selection_and_text(selection: str, text_value: str) -> str | None:
        selection = selection.strip()
        text_value = text_value.strip()
        if selection and text_value:
            return f"{selection} - {text_value}"
        if text_value:
            return text_value
        if selection:
            return selection
        return None

    def save_pdf(self) -> None:
        try:
            document = self._collect_document()
        except ValueError as exc:
            messagebox.showerror("입력 오류", str(exc))
            return

        initial = default_filename()
        file_path = filedialog.asksaveasfilename(
            title="PDF 저장",
            defaultextension=".pdf",
            filetypes=[("PDF 파일", "*.pdf")],
            initialfile=initial,
        )
        if not file_path:
            return

        output_path = generate_pdf(document, Path(file_path))
        messagebox.showinfo("완료", f"PDF가 저장되었습니다.\n{output_path}")

    def print_document(self) -> None:
        try:
            document = self._collect_document()
        except ValueError as exc:
            messagebox.showerror("입력 오류", str(exc))
            return

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / default_filename()
            generate_pdf(document, temp_path)
            print_pdf(temp_path)
            messagebox.showinfo("인쇄 요청", "PDF 인쇄 명령을 전송했습니다.")

    def reset_form(self) -> None:
        self.company_var.set("")
        self.date_var.set(datetime.today().strftime("%Y-%m-%d"))
        self.items.clear()
        self._refresh_items_tree()
        self.cause_choice_var.set("")
        self.repair_choice_var.set("")
        self.cause_text.delete("1.0", tk.END)
        self.repair_text.delete("1.0", tk.END)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = QuoteApp()
    app.run()


if __name__ == "__main__":
    main()
