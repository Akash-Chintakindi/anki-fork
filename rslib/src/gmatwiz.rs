// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! GMATWiz mobile helpers.
//!
//! Small, JSON-returning wrappers so the iOS app can open a collection and run
//! a real review session through the SHARED engine, without re-encoding
//! protobuf in Swift. All scheduling goes through the real scheduler
//! (`get_queued_cards` / `answer_card`); nothing is reimplemented here.

use std::collections::HashMap;

use serde_json::json;

use crate::prelude::*;
use crate::scheduler::answering::CardAnswer;
use crate::scheduler::answering::Rating;
use crate::search::SortMode;
use crate::timestamp::TimestampMillis;

// Give-up thresholds mirror qt/aqt/mediasrv.py (PRD Section 4).
const MEM_MIN_REVIEWS: i64 = 150;
const PERF_MIN_ATTEMPTS: usize = 50;
const PERF_MIN_PER_TOPIC: usize = 8;
const READY_MIN_COVERAGE: f64 = 50.0;
const READY_MIN_REVIEWS: i64 = 200;
const READY_MIN_ATTEMPTS: usize = 50;
const READY_MAX_ECE: f64 = 0.10;
const QUANT_TOPIC_TOTAL: f64 = 18.0;
const TARGET_RETENTION: f64 = 0.9;

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

    /// Map GMAT card id -> topic (bounded by the GMAT deck size).
    fn gmat_card_topics(&mut self) -> Result<HashMap<i64, String>> {
        let cids = self.search_cards("note:\"GMAT PS\"", SortMode::NoOrder)?;
        let mut note_topic: HashMap<i64, String> = HashMap::new();
        let mut map = HashMap::new();
        for cid in cids {
            let Some(card) = self.storage.get_card(cid)? else {
                continue;
            };
            let nid = card.note_id();
            let topic = if let Some(t) = note_topic.get(&nid.0) {
                t.clone()
            } else {
                let Some(note) = self.storage.get_note(nid)? else {
                    continue;
                };
                let names = self.storage.get_field_names(note.notetype_id)?;
                let vals = note.fields();
                let t = names
                    .iter()
                    .position(|n| n == "Topic")
                    .and_then(|i| vals.get(i))
                    .cloned()
                    .unwrap_or_default();
                note_topic.insert(nid.0, t.clone());
                t
            };
            map.insert(cid.0, topic);
        }
        Ok(map)
    }

    /// The three honest scores (Memory, Performance, Readiness) as JSON, mirroring
    /// the desktop mediasrv logic so the phone shows the same numbers + give-up
    /// abstentions. Computed from the review log + collection data.
    pub fn gmat_scores_json(&mut self) -> Result<String> {
        let now = TimestampMillis::now().0 / 1000;
        let card_topics = self.gmat_card_topics()?;
        let topics_covered: std::collections::HashSet<&String> = card_topics
            .values()
            .filter(|t| !t.is_empty())
            .collect();
        let coverage_pct = 100.0 * topics_covered.len() as f64 / QUANT_TOPIC_TOTAL;

        let memory = self.gmat_memory_json(now)?;
        let performance = self.gmat_performance_json(&card_topics, now)?;
        let readiness = self.gmat_readiness_json(&memory, &performance, coverage_pct, now);

        Ok(json!({
            "memory": memory,
            "performance": performance,
            "readiness": readiness,
            "topics_covered": topics_covered.len(),
            "topics_total": QUANT_TOPIC_TOTAL as i64,
        })
        .to_string())
    }

    fn gmat_memory_json(&self, now: i64) -> Result<serde_json::Value> {
        let total: i64 = self.storage.db.query_row(
            "select count() from revlog where ease between 1 and 4",
            [],
            |r| r.get(0),
        )?;
        if total < MEM_MIN_REVIEWS {
            return Ok(json!({
                "status": "abstain",
                "reviews": total,
                "reviews_required": MEM_MIN_REVIEWS,
                "reason": format!("Need {MEM_MIN_REVIEWS} graded reviews; you have {total}."),
                "updated_ts": now,
            }));
        }
        let passed: i64 = self.storage.db.query_row(
            "select count() from revlog where ease between 2 and 4",
            [],
            |r| r.get(0),
        )?;
        let observed = passed as f64 / total as f64;
        let se = (observed * (1.0 - observed) / total as f64).sqrt();
        let target = TARGET_RETENTION;

        let mut stmt = self.storage.db.prepare(
            "select case when lastIvl<=3 then 0 when lastIvl<=7 then 1 \
             when lastIvl<=21 then 2 when lastIvl<=60 then 3 else 4 end as b, \
             count(), sum(case when ease between 2 and 4 then 1 else 0 end) \
             from revlog where ease between 1 and 4 and lastIvl >= 1 group by b order by b",
        )?;
        let labels = ["1-3d", "4-7d", "8-21d", "22-60d", "60d+"];
        let rows: Vec<(i64, i64, i64)> = stmt
            .query_map([], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)))?
            .collect::<rusqlite::Result<_>>()?;
        let binned_total: i64 = rows.iter().map(|r| r.1).sum::<i64>().max(1);
        let mut ece = 0.0;
        let mut bins = Vec::new();
        for (b, n, p) in &rows {
            let obs = if *n > 0 { *p as f64 / *n as f64 } else { 0.0 };
            bins.push(json!({
                "label": labels[(*b).clamp(0, 4) as usize],
                "observed": (obs * 1000.0).round() / 1000.0,
                "n": n,
            }));
            ece += (*n as f64 / binned_total as f64) * (obs - target).abs();
        }
        Ok(json!({
            "status": "shown",
            "point": (observed * 100.0).round() as i64,
            "low": ((observed - 1.96 * se).max(0.0) * 100.0).round() as i64,
            "high": ((observed + 1.96 * se).min(1.0) * 100.0).round() as i64,
            "reviews": total,
            "target": (target * 100.0).round() as i64,
            "ece": (ece * 1000.0).round() / 1000.0,
            "calibrated": ece <= 0.10,
            "bins": bins,
            "updated_ts": now,
        }))
    }

    fn gmat_performance_json(
        &self,
        card_topics: &HashMap<i64, String>,
        now: i64,
    ) -> Result<serde_json::Value> {
        if card_topics.is_empty() {
            return Ok(json!({
                "status": "abstain", "attempts": 0,
                "attempts_required": PERF_MIN_ATTEMPTS,
                "reason": "No GMAT questions yet.", "updated_ts": now,
            }));
        }
        let mut stmt = self
            .storage
            .db
            .prepare("select cid, ease from revlog where lastIvl = 0 and ease between 1 and 4")?;
        let raw: Vec<(i64, i64)> = stmt
            .query_map([], |r| Ok((r.get(0)?, r.get(1)?)))?
            .collect::<rusqlite::Result<_>>()?;
        let attempts: Vec<(i64, u8)> = raw
            .into_iter()
            .filter(|(cid, _)| card_topics.contains_key(cid))
            .map(|(cid, ease)| (cid, if ease >= 2 { 1 } else { 0 }))
            .collect();
        let total = attempts.len();
        if total < PERF_MIN_ATTEMPTS {
            return Ok(json!({
                "status": "abstain", "attempts": total,
                "attempts_required": PERF_MIN_ATTEMPTS,
                "reason": format!("Need {PERF_MIN_ATTEMPTS} new-question attempts; you have {total}."),
                "updated_ts": now,
            }));
        }
        let correct: usize = attempts.iter().map(|(_, ok)| *ok as usize).sum();
        let acc = correct as f64 / total as f64;
        let se = (acc * (1.0 - acc) / total as f64).sqrt();

        // per-topic accuracy (only where >= PERF_MIN_PER_TOPIC)
        let mut per_topic: HashMap<&str, (usize, usize)> = HashMap::new();
        for (cid, ok) in &attempts {
            let t = card_topics.get(cid).map(String::as_str).unwrap_or("");
            let e = per_topic.entry(t).or_default();
            e.0 += *ok as usize;
            e.1 += 1;
        }
        let mut weak: Vec<serde_json::Value> = per_topic
            .iter()
            .filter(|(_, (_, n))| *n >= PERF_MIN_PER_TOPIC)
            .map(|(t, (c, n))| {
                json!({"topic": t, "accuracy": (*c as f64 / *n as f64 * 1000.0).round() / 1000.0, "n": n})
            })
            .collect();
        weak.sort_by(|a, b| {
            a["accuracy"].as_f64().partial_cmp(&b["accuracy"].as_f64()).unwrap()
        });
        weak.truncate(5);

        // held-out per-topic model vs global-mean baseline (Brier)
        let train: Vec<&(i64, u8)> = attempts.iter().filter(|(cid, _)| cid % 10 < 7).collect();
        let test: Vec<&(i64, u8)> = attempts.iter().filter(|(cid, _)| cid % 10 >= 7).collect();
        let eval = if !train.is_empty() && !test.is_empty() {
            let g_mean =
                train.iter().map(|(_, ok)| *ok as f64).sum::<f64>() / train.len() as f64;
            let mut tt: HashMap<&str, (f64, f64)> = HashMap::new();
            for (cid, ok) in &train {
                let t = card_topics.get(cid).map(String::as_str).unwrap_or("");
                let e = tt.entry(t).or_default();
                e.0 += *ok as f64;
                e.1 += 1.0;
            }
            let base = test
                .iter()
                .map(|(_, ok)| (g_mean - *ok as f64).powi(2))
                .sum::<f64>()
                / test.len() as f64;
            let model = test
                .iter()
                .map(|(cid, ok)| {
                    let t = card_topics.get(cid).map(String::as_str).unwrap_or("");
                    let pred = tt.get(t).map(|(c, n)| c / n).unwrap_or(g_mean);
                    (pred - *ok as f64).powi(2)
                })
                .sum::<f64>()
                / test.len() as f64;
            json!({
                "baseline_brier": (base * 10000.0).round() / 10000.0,
                "model_brier": (model * 10000.0).round() / 10000.0,
                "beats_baseline": model <= base,
                "test_n": test.len(),
            })
        } else {
            serde_json::Value::Null
        };

        Ok(json!({
            "status": "shown",
            "point": (acc * 100.0).round() as i64,
            "low": ((acc - 1.96 * se).max(0.0) * 100.0).round() as i64,
            "high": ((acc + 1.96 * se).min(1.0) * 100.0).round() as i64,
            "attempts": total,
            "weak_topics": weak,
            "eval": eval,
            "updated_ts": now,
        }))
    }

    fn gmat_readiness_json(
        &self,
        memory: &serde_json::Value,
        performance: &serde_json::Value,
        coverage_pct: f64,
        now: i64,
    ) -> serde_json::Value {
        let reviews = memory.get("reviews").and_then(|v| v.as_i64()).unwrap_or(0);
        let attempts = performance
            .get("attempts")
            .and_then(|v| v.as_i64())
            .unwrap_or(0) as usize;
        let ece = memory.get("ece").and_then(|v| v.as_f64());
        let mut unmet = Vec::new();
        if coverage_pct < READY_MIN_COVERAGE {
            unmet.push(format!(
                "topic coverage {}% (need {}%)",
                coverage_pct.round(),
                READY_MIN_COVERAGE as i64
            ));
        }
        if reviews < READY_MIN_REVIEWS {
            unmet.push(format!("{reviews} reviews (need {READY_MIN_REVIEWS})"));
        }
        if attempts < READY_MIN_ATTEMPTS {
            unmet.push(format!(
                "{attempts} application attempts (need {READY_MIN_ATTEMPTS})"
            ));
        }
        if ece.map(|e| e > READY_MAX_ECE).unwrap_or(true) {
            unmet.push("memory not yet calibrated (ECE <= 0.10)".to_string());
        }
        if !unmet.is_empty() {
            return json!({
                "status": "abstain",
                "unmet": unmet,
                "reason": "A confident number with no evidence is just a guess.",
                "updated_ts": now,
            });
        }
        let acc = performance["point"].as_f64().unwrap_or(0.0) / 100.0;
        let acc_low = performance["low"].as_f64().unwrap_or(0.0) / 100.0;
        let acc_high = performance["high"].as_f64().unwrap_or(0.0) / 100.0;
        let to_q = |a: f64| -> i64 {
            (70.0 + (a - 0.40) * (88.0 - 70.0) / (0.90 - 0.40))
                .clamp(60.0, 90.0)
                .round() as i64
        };
        let confidence = if coverage_pct >= 80.0 && attempts >= 150 {
            "medium"
        } else {
            "low"
        };
        json!({
            "status": "shown",
            "section": "Quant",
            "point": to_q(acc),
            "low": to_q(acc_low),
            "high": to_q(acc_high),
            "scale": "GMAT Focus Quant section (60-90)",
            "confidence": confidence,
            "method": "Heuristic map from held-out first-exposure accuracy; not yet validated against official practice-test scores.",
            "total_reason": "Total (205-805) needs Verbal + Data Insights data (not yet in scope).",
            "updated_ts": now,
        })
    }
}
