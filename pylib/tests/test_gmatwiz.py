# Copyright: GMATWiz contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

# coding: utf-8

import anki.gmatwiz as gw
from tests.shared import getEmptyCol


def _import_two_topics(col):
    questions = [
        {
            "stem": "If 2x + 3 = 11, what is x?",
            "options": {"A": "2", "B": "3", "C": "4", "D": "5", "E": "6"},
            "correct": "C",
            "explanation": "2x = 8, so x = 4.",
            "topic": "weak",
            "difficulty": "easy",
            "source": "test",
        },
        {
            "stem": "What is 15% of 80?",
            "options": {"A": "8", "B": "10", "C": "12", "D": "14", "E": "16"},
            "correct": "C",
            "explanation": "0.15 * 80 = 12.",
            "topic": "strong",
            "difficulty": "easy",
            "source": "test",
        },
    ]
    return gw.import_questions(col, questions, "GMAT::Quant")


def test_set_topic_mastery_roundtrip_and_undo():
    """Drives the new Rust scheduler change end to end from Python."""
    col = getEmptyCol()
    assert _import_two_topics(col) == 2

    # The new backend RPC updates exactly the cards tagged with the topic.
    out = col._backend.set_topic_mastery(topic="weak", mastery=0.1)
    assert out.count == 1

    # Re-applying the same value is a no-op (proves the value persisted).
    assert col._backend.set_topic_mastery(topic="weak", mastery=0.1).count == 0

    # A different topic touches its own card only.
    assert col._backend.set_topic_mastery(topic="strong", mastery=0.9).count == 1

    # Undo reverts the most recent change, so re-applying counts 1 again.
    col.undo()
    assert col._backend.set_topic_mastery(topic="strong", mastery=0.9).count == 1


def test_topic_aware_scheduling_toggle_is_off_by_default():
    col = getEmptyCol()
    # Collection bool configs default to false; the feature must be opt-in.
    assert col.get_config("topicAwareScheduling", False) is False
