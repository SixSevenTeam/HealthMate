"""Проверка безопасности медицинских рекомендаций.

Обеспечивает, что рекомендуемые препараты:
1. Не вызывают аллергических реакций у пользователя.
2. Не взаимодействуют опасно с текущими препаратами пользователя.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import structlog

from rag.domain.events import Medication

log = structlog.get_logger()


@dataclass
class SafetyWarning:
    """Предупреждение о небезопасности препарата для данного профиля."""

    type: Literal["contraindication_allergy", "drug_interaction", "chronic_condition"]
    medication: str
    reason: str
    severity: Literal["high", "medium", "low"]


class SafetyChecker:
    """Проверяет безопасность препаратов на основе профиля пользователя.

    Используется на этапе генерации рекомендаций (Этап 3):
    препараты, получившие предупреждения высокой серьёзности,
    исключаются из рекомендаций или помечаются явным предупреждением.
    """

    def check_allergies(
        self,
        medications: list[str],
        allergies: list[str],
    ) -> list[SafetyWarning]:
        """Проверяет препараты на аллергические реакции.

        Использует простой keyword-matching с нормализацией
        (игнорирование регистра, учёт альтернативных названий).

        Args:
            medications: Список рекомендуемых препаратов.
            allergies: Список аллергенов из профиля пользователя.

        Returns:
            Список предупреждений для опасных сочетаний.
        """
        # TODO:
        # for med in medications:
        #   for allergen in allergies:
        #     if normalize(med) == normalize(allergen) or is_synonym(med, allergen):
        #       warnings.append(SafetyWarning(..., severity="high"))
        log.warning("check_allergies_not_implemented")
        pass

    def check_drug_interactions(
        self,
        new_medications: list[str],
        current_medications: list[Medication],
    ) -> list[SafetyWarning]:
        """Проверяет взаимодействие новых препаратов с текущими.

        Args:
            new_medications: Список рекомендуемых препаратов.
            current_medications: Текущие препараты из профиля пользователя.

        Returns:
            Список предупреждений об опасных взаимодействиях.
        """
        # TODO: использовать базу взаимодействий (drugbank или подобную)
        # Простейший вариант: hardcoded пары известных взаимодействий
        log.warning("check_drug_interactions_not_implemented")
        pass

    def check_chronic_conditions(
        self,
        medications: list[str],
        conditions: list[str],
    ) -> list[SafetyWarning]:
        """Проверяет совместимость препаратов с хроническими диагнозами.

        Например, НПВС противопоказаны при язвенной болезни.

        Args:
            medications: Список рекомендуемых препаратов.
            conditions: Список хронических диагнозов пользователя.
        """
        # TODO: база противопоказаний по нозологиям
        log.warning("check_chronic_conditions_not_implemented")
        pass


_safety_checker: SafetyChecker | None = None


def get_safety_checker() -> SafetyChecker:
    """Возвращает singleton-экземпляр SafetyChecker."""
    global _safety_checker
    if _safety_checker is None:
        _safety_checker = SafetyChecker()
    return _safety_checker
