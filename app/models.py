"""Data models and enumerations for the quotation application."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


DEFAULT_CAUSES = [
    "사용자 과실",
    "소모품 교체 필요",
    "정기 점검",
    "제품 결함",
]

DEFAULT_REPAIRS = [
    "부품 교체",
    "소프트웨어 업데이트",
    "현장 점검",
    "원격 지원",
]


@dataclass
class QuoteItem:
    """단일 품목 정보를 저장하는 데이터 클래스."""

    name: str
    model_no: str
    quantity: int
    unit: str
    unit_price: float
    amount: float

    def to_row(self) -> List[str]:
        """Treeview 등에 표시하기 위한 문자열 리스트를 반환한다."""
        return [
            self.name,
            self.model_no,
            str(self.quantity),
            self.unit,
            f"{self.unit_price:,.0f}",
            f"{self.amount:,.0f}",
        ]


@dataclass
class QuoteDocument:
    """견적서 전체 데이터를 표현하는 데이터 클래스."""

    company_name: str
    quotation_date: date
    items: List[QuoteItem] = field(default_factory=list)
    cause: Optional[str] = None
    repair_detail: Optional[str] = None

    @property
    def total_amount(self) -> float:
        return sum(item.amount for item in self.items)
