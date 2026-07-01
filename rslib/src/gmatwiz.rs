// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! GMATWiz mobile helpers.
//!
//! Small, JSON-returning wrappers so the iOS app can open a collection and run
//! a real review session through the SHARED engine, without re-encoding
//! protobuf in Swift. All scheduling goes through the real scheduler
//! (`get_queued_cards` / `answer_card`); nothing is reimplemented here.

use serde_json::json;

use crate::prelude::*;
use crate::scheduler::answering::CardAnswer;
use crate::scheduler::answering::Rating;
use crate::timestamp::TimestampMillis;

impl Collection {
    fn gmat_select_deck(&mut self, deck_name: &str) -> Result<()> {
        if let Some(did) = self.storage.get_deck_id(deck_name)? {
            self.set_current_deck(did)?;
        }
        Ok(())
    }

    /// Current review state for `deck_name` as JSON: queue counts plus the next
    /// card (id, stem, options, correct, explanation, topic), or `card: null`.
    pub fn gmat_mobile_state_json(&mut self, deck_name: &str) -> Result<String> {
        self.gmat_select_deck(deck_name)?;
        let queued = self.get_queued_cards(1, false)?;
        let card_json = if let Some(qc) = queued.cards.first() {
            let note = self
                .storage
                .get_note(qc.card.note_id())?
                .or_not_found(qc.card.note_id())?;
            let names = self.storage.get_field_names(note.notetype_id)?;
            let vals = note.fields();
            let field = |name: &str| -> String {
                names
                    .iter()
                    .position(|n| n == name)
                    .and_then(|i| vals.get(i))
                    .cloned()
                    .unwrap_or_default()
            };
            json!({
                "id": qc.card.id().0,
                "stem": field("Stem"),
                "options": {
                    "A": field("OptionA"),
                    "B": field("OptionB"),
                    "C": field("OptionC"),
                    "D": field("OptionD"),
                    "E": field("OptionE"),
                },
                "correct": field("Correct"),
                "explanation": field("Explanation"),
                "topic": field("Topic"),
            })
        } else {
            serde_json::Value::Null
        };
        Ok(json!({
            "new": queued.new_count,
            "learning": queued.learning_count,
            "review": queued.review_count,
            "card": card_json,
        })
        .to_string())
    }

    /// Answer the current card through the real scheduler (Good if `correct`,
    /// else Again), writing a revlog entry. This is a genuine review.
    pub fn gmat_mobile_answer(&mut self, card_id: i64, correct: bool) -> Result<()> {
        let queued = self.get_queued_cards(1, false)?;
        let qc = queued
            .cards
            .into_iter()
            .find(|c| c.card.id().0 == card_id)
            .or_invalid("requested card is not at the front of the queue")?;
        let states = qc.states;
        let mut answer = CardAnswer {
            card_id: qc.card.id(),
            current_state: states.current,
            new_state: if correct { states.good } else { states.again },
            rating: if correct { Rating::Good } else { Rating::Again },
            answered_at: TimestampMillis::now(),
            milliseconds_taken: 1500,
            custom_data: None,
            from_queue: true,
        };
        self.answer_card(&mut answer)?;
        Ok(())
    }
}
