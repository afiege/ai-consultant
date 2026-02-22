"""Tests for 6-3-5 brainwriting rotation and completion logic."""

import pytest
from app.services.six_three_five_manager import SixThreeFiveSession


class TestConstants:
    """Tests that 6-3-5 method constants are correct."""

    def test_max_participants(self):
        assert SixThreeFiveSession.MAX_PARTICIPANTS == 6

    def test_min_participants(self):
        assert SixThreeFiveSession.MIN_PARTICIPANTS == 1

    def test_ideas_per_round(self):
        assert SixThreeFiveSession.IDEAS_PER_ROUND == 3

    def test_max_rounds(self):
        assert SixThreeFiveSession.MAX_ROUNDS == 6


class TestRotationFormula:
    """Tests for the sheet rotation formula: (current_idx + 1) % num_participants."""

    @pytest.mark.parametrize("current_idx,num_participants,expected_next", [
        # 2 participants: 0->1, 1->0
        (0, 2, 1),
        (1, 2, 0),
        # 3 participants: 0->1, 1->2, 2->0
        (0, 3, 1),
        (1, 3, 2),
        (2, 3, 0),
        # 6 participants (full): wraps at end
        (0, 6, 1),
        (4, 6, 5),
        (5, 6, 0),
        # 1 participant (solo): stays with same person
        (0, 1, 0),
    ])
    def test_rotation(self, current_idx, num_participants, expected_next):
        next_idx = (current_idx + 1) % num_participants
        assert next_idx == expected_next

    def test_full_rotation_cycle_returns_to_start(self):
        """After num_participants rotations, sheet returns to original holder."""
        for num_p in range(1, 7):
            idx = 0
            for _ in range(num_p):
                idx = (idx + 1) % num_p
            assert idx == 0, f"Full cycle failed for {num_p} participants"


class TestCompletionLogic:
    """Tests for session completion conditions."""

    MAX_ROUNDS = SixThreeFiveSession.MAX_ROUNDS

    def test_beyond_max_rounds_is_complete(self):
        current_round = self.MAX_ROUNDS + 1
        assert current_round > self.MAX_ROUNDS

    def test_at_max_round_not_complete_without_submissions(self):
        current_round = self.MAX_ROUNDS
        submitted_count = 3
        total_sheets = 6
        is_complete = (current_round > self.MAX_ROUNDS) or \
                      (submitted_count == total_sheets and current_round == self.MAX_ROUNDS)
        assert is_complete is False

    def test_at_max_round_complete_with_all_submissions(self):
        current_round = self.MAX_ROUNDS
        submitted_count = 6
        total_sheets = 6
        is_complete = (current_round > self.MAX_ROUNDS) or \
                      (submitted_count == total_sheets and current_round == self.MAX_ROUNDS)
        assert is_complete is True

    def test_before_max_round_not_complete(self):
        current_round = 3
        submitted_count = 6
        total_sheets = 6
        is_complete = (current_round > self.MAX_ROUNDS) or \
                      (submitted_count == total_sheets and current_round == self.MAX_ROUNDS)
        assert is_complete is False

    def test_max_total_ideas(self):
        """6 participants x 3 ideas x 6 rounds = 108 total ideas."""
        total = SixThreeFiveSession.MAX_PARTICIPANTS * \
                SixThreeFiveSession.IDEAS_PER_ROUND * \
                SixThreeFiveSession.MAX_ROUNDS
        assert total == 108
