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

    _SYNONYM_GROUPS: list[set[str]] = [
        {"аспирин", "ацетилсалициловая кислота", "аск"},
        {"парацетамол", "ацетаминофен"},
        {"ибупрофен", "нурофен"},
        {"диклофенак", "вольтарен"},
        {"омепразол", "омез"},
        {"амоксициллин", "амоксиклав", "аугментин"},
        {"пенициллин", "амоксициллин", "ампициллин"},
    ]

    _INTERACTION_PAIRS: dict[frozenset[str], dict] = {
        frozenset({"варфарин", "аспирин"}): {
            "reason": "Повышенный риск кровотечения", "severity": "high",
        },
        frozenset({"метотрексат", "ибупрофен"}): {
            "reason": "Повышение токсичности метотрексата", "severity": "high",
        },
        frozenset({"литий", "ибупрофен"}): {
            "reason": "Повышение концентрации лития", "severity": "high",
        },
        frozenset({"метформин", "алкоголь"}): {
            "reason": "Риск лактоацидоза", "severity": "medium",
        },
        frozenset({"антибиотик", "антацид"}): {
            "reason": "Снижение всасывания антибиотика", "severity": "medium",
        },
    }

    _CONDITION_CONTRAINDICATIONS: dict[tuple[str, str], dict] = {
        ("ибупрофен", "язвенная болезнь"): {
            "reason": "НПВС противопоказаны при язвенной болезни", "severity": "high",
        },
        ("аспирин", "язвенная болезнь"): {
            "reason": "Аспирин противопоказан при язвенной болезни", "severity": "high",
        },
        ("метформин", "почечная недостаточность"): {
            "reason": "Метформин противопоказан при почечной недостаточности", "severity": "high",
        },
        ("бета-блокатор", "бронхиальная астма"): {
            "reason": "Бета-блокаторы могут ухудшить течение астмы", "severity": "high",
        },
    }

    @staticmethod
    def _is_synonym(med: str, allergen: str) -> bool:
        """Проверяет, являются ли препарат и аллерген синонимами."""
        for group in SafetyChecker._SYNONYM_GROUPS:
            if med in group and allergen in group:
                return True
        return False

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
        warnings: list[SafetyWarning] = []
        norm_allergies = [a.lower().strip() for a in allergies]

        if isinstance(medications, str):
            medications = [medications]

        for med in medications:
            med_lower = med.lower().strip()
            for allergen in norm_allergies:
                if allergen in med_lower or med_lower in allergen:
                    warnings.append(SafetyWarning(
                        type="contraindication_allergy",
                        medication=med,
                        reason=f"Аллергия на {allergen}",
                        severity="high",
                    ))
                elif self._is_synonym(med_lower, allergen):
                    warnings.append(SafetyWarning(
                        type="contraindication_allergy",
                        medication=med,
                        reason=f"Аллергия на {allergen} (синоним/группа)",
                        severity="high",
                    ))

        if warnings:
            log.warning("allergy_warnings_found", count=len(warnings))
        return warnings

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
        warnings: list[SafetyWarning] = []

        current_names = [m.name.lower().strip() for m in current_medications]

        for new_med in new_medications:
            new_lower = new_med.lower().strip()
            for cur_name in current_names:
                pair = frozenset({new_lower, cur_name})
                if pair in self._INTERACTION_PAIRS:
                    info = self._INTERACTION_PAIRS[pair]
                    warnings.append(SafetyWarning(
                        type="drug_interaction",
                        medication=new_med,
                        reason=info["reason"],
                        severity=info["severity"],
                    ))

        if warnings:
            log.warning("drug_interaction_warnings", count=len(warnings))
        return warnings

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
        warnings: list[SafetyWarning] = []
        norm_conditions = [c.lower().strip() for c in conditions]

        for med in medications:
            med_lower = med.lower().strip()
            for cond in norm_conditions:
                pair = (med_lower, cond)
                if pair in self._CONDITION_CONTRAINDICATIONS:
                    info = self._CONDITION_CONTRAINDICATIONS[pair]
                    warnings.append(SafetyWarning(
                        type="chronic_condition",
                        medication=med,
                        reason=info["reason"],
                        severity=info["severity"],
                    ))

        if warnings:
            log.warning("chronic_condition_warnings", count=len(warnings))
        return warnings


_safety_checker: SafetyChecker | None = None


def get_safety_checker() -> SafetyChecker:
    """Возвращает singleton-экземпляр SafetyChecker."""
    global _safety_checker
    if _safety_checker is None:
        _safety_checker = SafetyChecker()
    return _safety_checker
