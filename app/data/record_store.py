from __future__ import annotations


class TradeRecordStore:
    def __init__(self) -> None:
        self._records: list[dict] = []

    def save(self, record: dict) -> dict:
        self._records.append(record)
        return record

    def list_all(self) -> list[dict]:
        return self._records.copy()
