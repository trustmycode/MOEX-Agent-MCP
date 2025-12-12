from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from agent_service.llm import build_evolution_llm_client_from_env

logger = logging.getLogger(__name__)


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
        llm_callback: Optional[Callable[[str], ParseResult | Awaitable[ParseResult]]] = None,
        min_confidence: float = 0.6,
    ) -> None:
        self.min_confidence = min_confidence
        self._llm_client = None
        if llm_callback is None:
            self._llm_client = build_evolution_llm_client_from_env()
        self.llm_callback = llm_callback or (
            (lambda q: self._llm_fallback(q)) if self._llm_client else None
        )

    async def parse_portfolio(self, query: Optional[str], allow_llm: bool = True) -> ParseResult:
        """
        Извлечь позиции портфеля из текста запроса.

        Args:
            query: Текст запроса пользователя.
            allow_llm: Разрешить ли LLM-fallback, если rule-based неуверен.
        """
        rule_result = self._parse_rule_based(query or "")
        if rule_result.has_positions and rule_result.confidence >= self.min_confidence:
            return rule_result

        if allow_llm and self.llm_callback and query:
            try:
                llm_result = self.llm_callback(query)
                if hasattr(llm_result, "__await__"):
                    llm_result = await llm_result  # type: ignore[assignment]
                if llm_result and llm_result.has_positions:
                    return llm_result
            except Exception as exc:
                # Не прерываем работу, если LLM недоступен
                logger.info("LLM fallback parse failed: %s", exc)

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

        positions = self._parse_natural_language_positions(query)

        pattern = re.compile(
            r"\b([A-Z]{2,6})\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*%?",
            re.IGNORECASE,
        )

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

    def _parse_natural_language_positions(self, query: str) -> list[dict[str, Any]]:
        """
        Более либеральный парсинг русских фраз: «20% в кэше», «30% в коротких ОФЗ (SU...)»,
        «50% в акциях SBER».
        """
        if not query:
            return []
        pattern = re.compile(
            r"(\d{1,3}(?:[.,]\d{1,2})?)\s*%?\s*(?:в|во)?\s*(?:акциях\s+|акции\s+|бумагах\s+)?"
            r"([A-Za-zА-Яа-я0-9._-]{2,24})(?:\s*\(\s*([A-Za-z0-9]{2,20})[^)]*\))?",
            re.IGNORECASE,
        )

        positions: dict[str, dict[str, Any]] = {}

        for weight_raw, asset_raw, paren_token in pattern.findall(query):
            try:
                weight = float(weight_raw.replace(",", "."))
            except ValueError:
                continue
            if weight > 1:
                weight = weight / 100.0

            ticker = self._resolve_ticker(asset_raw, paren_token)
            if not ticker:
                continue

            if ticker in positions:
                positions[ticker]["weight"] += weight
            else:
                positions[ticker] = {"ticker": ticker, "weight": weight}

        return list(positions.values())

    @staticmethod
    def _resolve_ticker(asset_raw: str, paren_token: Optional[str]) -> Optional[str]:
        asset_token = re.sub(r"[^A-Za-zА-Яа-я0-9]", "", asset_raw).lower()
        paren_clean = None
        if paren_token:
            paren_match = re.match(r"([A-Za-z0-9]{2,20})", paren_token)
            if paren_match:
                paren_clean = paren_match.group(1).upper()

        synonyms = {
            "cash": "CASH",
            "кэш": "CASH",
            "наличные": "CASH",
            "наличн": "CASH",
            "ofz": "OFZ",
            "офз": "OFZ",
            "obligation": "OFZ",
            "облигации": "OFZ",
            "короткихофз": "OFZ",
            "короткофонз": "OFZ",
        }

        for key, mapped in synonyms.items():
            if asset_token.startswith(key):
                return mapped

        if 2 <= len(asset_token) <= 12 and re.match(r"^[A-Za-z0-9]+$", asset_token):
            return asset_token.upper()

        return paren_clean

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

    def _extract_json(self, raw: str) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
        return {}

    async def _llm_fallback(self, query: str) -> ParseResult:
        """
        LLM-фолбэк: просим модель вернуть JSON с positions.
        """
        if not self._llm_client:
            return ParseResult(positions=[], confidence=0.0, source="llm", message=None)

        system_prompt = (
            "Ты извлекаешь портфель из русского текста. "
            "Верни только JSON: {\"positions\": [{\"ticker\": \"SBER\", \"weight\": 0.5}]}. "
            "weight — доля от 0 до 1. Если указан ISIN/тикер в скобках — используй его. "
            "Не добавляй пояснений и текста вне JSON."
        )
        user_prompt = f"Запрос: {query}\nВерни только JSON."

        raw = ""
        try:
            raw = await self._llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=400,
            )
        except Exception as exc:
            logger.info("LLM generation failed: %s", exc)
            return ParseResult(positions=[], confidence=0.0, source="llm", message=str(exc))

        payload = self._extract_json(raw)
        positions_raw = payload.get("positions") or []
        positions: list[dict[str, Any]] = []
        for item in positions_raw:
            if not isinstance(item, dict):
                continue
            ticker = (
                str(item.get("ticker") or item.get("isin") or "").strip().upper()
            )
            if not ticker:
                continue
            weight = item.get("weight")
            try:
                weight_val = float(weight)
            except (TypeError, ValueError):
                weight_val = None
            if weight_val is None:
                continue
            positions.append({"ticker": ticker, "weight": weight_val})

        positions = self._normalize_weights(positions)
        confidence = 0.85 if positions else 0.0
        message = None if positions else "LLM не вернул позиции"

        return ParseResult(
            positions=positions,
            confidence=confidence,
            source="llm",
            message=message,
        )
