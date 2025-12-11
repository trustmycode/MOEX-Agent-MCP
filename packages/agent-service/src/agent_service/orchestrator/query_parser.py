from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class ParseResult:
    """Результат парсинга пользовательского запроса."""

    positions: list[dict[str, Any]]
    confidence: float
    source: str
    message: Optional[str] = None

    @property
    def has_positions(self) -> bool:
        return bool(self.positions)


class QueryParser:
    """
    Парсер пользовательского запроса (rule-based + опциональный LLM fallback).
    """

    def __init__(
        self,
        llm_callback: Optional[Callable[[str], ParseResult]] = None,
        min_confidence: float = 0.6,
    ) -> None:
        self.llm_callback = llm_callback
        self.min_confidence = min_confidence

    def parse_portfolio(self, query: str, allow_llm: bool = True) -> ParseResult:
        """
        Извлечь позиции портфеля из текста запроса.

        Args:
            query: Текст запроса пользователя.
            allow_llm: Разрешить ли LLM-fallback, если rule-based неуверен.
        """
        rule_result = self._parse_rule_based(query)
        if rule_result.has_positions and rule_result.confidence >= self.min_confidence:
            return rule_result

        if allow_llm and self.llm_callback:
            try:
                llm_result = self.llm_callback(query)
                if llm_result and llm_result.has_positions:
                    return llm_result
            except Exception:
                # Не прерываем работу, если LLM недоступен
                pass

        # Возвращаем то, что смог rule-based (возможно пустое), без догадок
        return rule_result

    # --- internal ---
    def _parse_rule_based(self, query: str) -> ParseResult:
        """
        Простой разбор тикеров и весов:
        - Тикеры A-Z 2..6 символов
        - Веса как проценты или доли (40%, 0.4)
        - Если весов нет — равные доли между найденными тикерами
        """
        if not query:
            return ParseResult(positions=[], confidence=0.0, source="rule", message=None)

        pattern = re.compile(
            r"\b([A-Z]{2,6})\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*%?",
            re.IGNORECASE,
        )
        positions: list[dict[str, Any]] = []

        for match in pattern.finditer(query):
            ticker = match.group(1).upper()
            weight_raw = match.group(2).replace(",", ".")
            try:
                weight_val = float(weight_raw)
            except ValueError:
                continue

            if weight_val > 1:
                weight_val = weight_val / 100.0

            positions.append({"ticker": ticker, "weight": weight_val})

        tickers_only: list[str] = []
        if not positions:
            ticker_pattern = re.compile(r"\b([A-Z]{2,6})\b", re.IGNORECASE)
            for ticker in ticker_pattern.findall(query):
                ticker_up = ticker.upper()
                if ticker_up not in tickers_only:
                    tickers_only.append(ticker_up)

            if tickers_only:
                equal_weight = round(1.0 / len(tickers_only), 4)
                positions = [{"ticker": t, "weight": equal_weight} for t in tickers_only]

        positions = self._normalize_weights(positions)

        confidence = 0.0
        if positions:
            has_explicit_weights = any(p.get("weight") not in (None, 0) for p in positions)
            confidence = 0.9 if has_explicit_weights else 0.6

        message = None
        if not positions:
            message = "Не удалось извлечь позиции из текста"

        return ParseResult(
            positions=positions,
            confidence=confidence,
            source="rule",
            message=message,
        )

    @staticmethod
    def _normalize_weights(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not positions:
            return positions
        total = sum((p.get("weight") or 0) for p in positions)
        if total <= 0:
            return positions
        return [
            {**p, "weight": round((p.get("weight") or 0) / total, 4)}
            for p in positions
        ]
