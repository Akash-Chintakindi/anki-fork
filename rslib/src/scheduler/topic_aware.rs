// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! GMATWiz topic-aware scheduling support.
//!
//! Stores a per-card topic mastery value (0.0-1.0) so the queue builder can
//! surface weaker-topic cards first. Only the surfacing ORDER changes; FSRS
//! intervals and memory state are never touched here.

use crate::prelude::*;
use crate::search::SortMode;

impl Collection {
    /// Set topic mastery for every card whose note is tagged with `topic`.
    ///
    /// Runs as a single undoable operation and returns the number of cards
    /// updated. Does not modify any FSRS/scheduling fields.
    pub fn set_topic_mastery(
        &mut self,
        topic: &str,
        mastery: f32,
    ) -> Result<OpOutput<usize>> {
        let mastery = mastery.clamp(0.0, 1.0);
        let search = format!("tag:{}", search_escape(topic));
        let cids = self.search_cards(&search, SortMode::NoOrder)?;
        self.transact(Op::UpdateCard, |col| {
            let usn = col.usn()?;
            let mut count = 0;
            for cid in cids {
                if let Some(mut card) = col.storage.get_card(cid)? {
                    if card.topic_mastery == Some(mastery) {
                        continue;
                    }
                    let original = card.clone();
                    card.topic_mastery = Some(mastery);
                    col.update_card_inner(&mut card, original, usn)?;
                    count += 1;
                }
            }
            Ok(count)
        })
    }
}

/// Escape characters that are meaningful inside an Anki search term so a topic
/// like `gmat::quant::algebra` is matched literally as a tag.
fn search_escape(text: &str) -> String {
    let escaped = text.replace('\\', "\\\\").replace('"', "\\\"");
    format!("\"{escaped}\"")
}

#[cfg(test)]
mod test {
    use crate::collection::Collection;
    use crate::config::BoolKey;
    use crate::prelude::*;

    /// Add a review card whose note carries `tag`; returns its card id.
    fn add_tagged_review_card(col: &mut Collection, field: &str, tag: &str) -> CardId {
        let nt = col.get_notetype_by_name("Basic").unwrap().unwrap();
        let mut note = nt.new_note();
        note.set_field(0, field).unwrap();
        note.tags = vec![tag.to_string()];
        col.add_note(&mut note, DeckId(1)).unwrap();
        let cid = col.storage.card_ids_of_notes(&[note.id]).unwrap()[0];
        let mut card = col.storage.get_card(cid).unwrap().unwrap();
        card.ctype = crate::card::CardType::Review;
        card.queue = crate::card::CardQueue::Review;
        card.due = 0;
        card.interval = 10;
        col.update_cards_maybe_undoable(vec![card], false).unwrap();
        cid
    }

    fn queue_card_order(col: &mut Collection) -> Vec<CardId> {
        col.get_queued_cards(100, false)
            .unwrap()
            .cards
            .into_iter()
            .map(|c| c.card.id)
            .collect()
    }

    #[test]
    fn set_topic_mastery_persists_and_counts() {
        let mut col = Collection::new();
        let cid = add_tagged_review_card(&mut col, "a", "weak");
        let out = col.set_topic_mastery("weak", 0.2).unwrap();
        assert_eq!(out.output, 1);
        // value round-trips through the data column
        let card = col.storage.get_card(cid).unwrap().unwrap();
        assert_eq!(card.topic_mastery, Some(0.2));
    }

    #[test]
    fn weak_topic_surfaces_first_when_enabled() {
        let mut col = Collection::new();
        let strong = add_tagged_review_card(&mut col, "strong", "strong");
        let weak = add_tagged_review_card(&mut col, "weak", "weak");
        col.set_topic_mastery("strong", 0.95).unwrap();
        col.set_topic_mastery("weak", 0.1).unwrap();

        col.set_config_bool(BoolKey::TopicAwareScheduling, true, false)
            .unwrap();
        let order = queue_card_order(&mut col);
        let weak_pos = order.iter().position(|c| *c == weak).unwrap();
        let strong_pos = order.iter().position(|c| *c == strong).unwrap();
        assert!(weak_pos < strong_pos, "weak topic should come first");
    }

    #[test]
    fn intervals_unchanged_regardless_of_toggle() {
        let mut col = Collection::new();
        let strong = add_tagged_review_card(&mut col, "strong", "strong");
        let weak = add_tagged_review_card(&mut col, "weak", "weak");
        col.set_topic_mastery("strong", 0.95).unwrap();
        col.set_topic_mastery("weak", 0.1).unwrap();

        // snapshot the FSRS-relevant fields that must never be touched by reordering
        let snapshot = |col: &mut Collection| -> Vec<(i64, u32, i32, u16)> {
            [weak, strong]
                .iter()
                .map(|&c| {
                    let card = col.storage.get_card(c).unwrap().unwrap();
                    (card.id.0, card.interval, card.due, card.ease_factor)
                })
                .collect()
        };

        col.set_config_bool(BoolKey::TopicAwareScheduling, false, false)
            .unwrap();
        let _ = queue_card_order(&mut col);
        let off = snapshot(&mut col);

        col.set_config_bool(BoolKey::TopicAwareScheduling, true, false)
            .unwrap();
        let _ = queue_card_order(&mut col);
        let on = snapshot(&mut col);

        // Reordering (Mechanism A) changes only surfacing order, never intervals.
        assert_eq!(off, on);
        assert_eq!(col.storage.get_card(weak).unwrap().unwrap().interval, 10);
        assert_eq!(col.storage.get_card(strong).unwrap().unwrap().interval, 10);
    }

    #[test]
    fn set_topic_mastery_is_undoable() {
        let mut col = Collection::new();
        let cid = add_tagged_review_card(&mut col, "a", "weak");
        col.set_topic_mastery("weak", 0.2).unwrap();
        assert_eq!(
            col.storage.get_card(cid).unwrap().unwrap().topic_mastery,
            Some(0.2)
        );
        col.undo().unwrap();
        assert_eq!(
            col.storage.get_card(cid).unwrap().unwrap().topic_mastery,
            None
        );
    }
}
