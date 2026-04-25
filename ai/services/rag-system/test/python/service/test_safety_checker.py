"""Tests for SafetyChecker."""

from __future__ import annotations

import pytest

from rag.medical.safety_checker import SafetyChecker, SafetyWarning
from rag.domain.events import Medication


class TestSafetyChecker:

    def setup_method(self):
        self.checker = SafetyChecker()

    # ── check_allergies ──────────────────────────────────────────────────

    def test_allergy_direct_match(self):
        warnings = self.checker.check_allergies(["аспирин"], ["аспирин"])
        assert len(warnings) == 1
        assert warnings[0].type == "contraindication_allergy"
        assert warnings[0].severity == "high"

    def test_allergy_case_insensitive(self):
        warnings = self.checker.check_allergies(["Аспирин"], ["аспирин"])
        assert len(warnings) == 1

    def test_allergy_substring_match(self):
        warnings = self.checker.check_allergies(["парацетамол"], ["парацетамол"])
        assert len(warnings) >= 1

    def test_allergy_synonym_match(self):
        warnings = self.checker.check_allergies(["нурофен"], ["ибупрофен"])
        assert len(warnings) == 1
        assert "синоним" in warnings[0].reason

    def test_allergy_no_match(self):
        warnings = self.checker.check_allergies(["омепразол"], ["пенициллин"])
        assert len(warnings) == 0

    def test_allergy_string_input(self):
        warnings = self.checker.check_allergies("аспирин", ["аспирин"])
        assert len(warnings) == 1

    def test_allergy_empty_lists(self):
        warnings = self.checker.check_allergies([], [])
        assert len(warnings) == 0

    # ── check_drug_interactions ──────────────────────────────────────────

    def test_drug_interaction_known_pair(self):
        current = [Medication(name="варфарин", dosage="5мг", frequency="1р/д")]
        warnings = self.checker.check_drug_interactions(["аспирин"], current)
        assert len(warnings) == 1
        assert warnings[0].type == "drug_interaction"
        assert "кровотечени" in warnings[0].reason.lower()

    def test_drug_interaction_no_match(self):
        current = [Medication(name="омепразол", dosage="20мг", frequency="1р/д")]
        warnings = self.checker.check_drug_interactions(["парацетамол"], current)
        assert len(warnings) == 0

    def test_drug_interaction_empty(self):
        warnings = self.checker.check_drug_interactions([], [])
        assert len(warnings) == 0

    def test_drug_interaction_methotrexate_ibuprofen(self):
        current = [Medication(name="метотрексат", dosage="10мг", frequency="1р/нед")]
        warnings = self.checker.check_drug_interactions(["ибупрофен"], current)
        assert len(warnings) == 1

    # ── check_chronic_conditions ─────────────────────────────────────────

    def test_chronic_condition_nsaid_ulcer(self):
        warnings = self.checker.check_chronic_conditions(
            ["ибупрофен"], ["язвенная болезнь"]
        )
        assert len(warnings) == 1
        assert warnings[0].type == "chronic_condition"

    def test_chronic_condition_aspirin_ulcer(self):
        warnings = self.checker.check_chronic_conditions(
            ["аспирин"], ["язвенная болезнь"]
        )
        assert len(warnings) == 1

    def test_chronic_condition_no_match(self):
        warnings = self.checker.check_chronic_conditions(
            ["парацетамол"], ["гипертония"]
        )
        assert len(warnings) == 0

    def test_chronic_condition_empty(self):
        warnings = self.checker.check_chronic_conditions([], [])
        assert len(warnings) == 0

    # ── _is_synonym ──────────────────────────────────────────────────────

    def test_is_synonym_true(self):
        assert SafetyChecker._is_synonym("парацетамол", "ацетаминофен") is True

    def test_is_synonym_false(self):
        assert SafetyChecker._is_synonym("парацетамол", "ибупрофен") is False

    def test_is_synonym_same_word(self):
        assert SafetyChecker._is_synonym("аспирин", "аспирин") is True
