// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! GMATWiz mobile helpers.
//!
//! Small, JSON-returning wrappers so the iOS app can open a collection and run
//! a real review session through the SHARED engine, without re-encoding
//! protobuf in Swift. All scheduling goes through the real scheduler
//! (`get_queued_cards` / `answer_card`); nothing is reimplemented here.

use std::collections::HashMap;
use std::collections::HashSet;

use chrono::Datelike;
use chrono::Duration;
use chrono::Local;
use chrono::NaiveDate;
use chrono::TimeZone;
use rand::seq::IndexedRandom;
use rand::seq::SliceRandom;
use rusqlite::params;
use serde_json::json;
use serde_json::Value;

use crate::config::BoolKey;
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
// GMAT Focus Quant pacing: 21 questions in 45 minutes ~= 128s per question.
const GMAT_TARGET_MS: i64 = 128_000;
// A full-length practice test only makes sense once the student has learned a
// meaningful slice of the syllabus AND is within striking distance of the exam -
// never on day one. (Tunable.)
const GMAT_TEST_MIN_LEARNED_FRAC: f64 = 0.5;
const GMAT_TEST_EXAM_WINDOW_DAYS: i64 = 28;

// The GMATWiz app state stored in collection config JSON. These (plus the
// `topicAwareScheduling` bool) are what we sync across devices via Firestore -
// NOT the whole collection. Keep in lock-step with the desktop mediasrv shape.
const GMAT_STATE_KEYS: &[&str] = &[
    "gmatProfile",
    "gmatPlan",
    "gmatDiagnosis",
    "gmatMocks",
    "gmatOfficialScores",
    "gmatLearned",
    "gmatErrorLog",
    "gmatRepairTopics",
    "gmatTimedDrill",
    "gmatLessonScheduled",
    "gmatTestsTaken",
    "gmatAiEnabled",
    // 3-tier assessment layer: per-topic quiz session history (the mastery
    // gate) and the application-attempt log the Performance reader folds in
    // (quiz/milestone answers, which never touch the scheduler/revlog).
    "gmatQuizzes",
    "gmatApplication",
];

// Assessment layer (mirrors qt/aqt/mediasrv.py). Quiz/milestone answers move
// mastery HARDER than a single drill; the SOFT mastery gate needs >=2 passing
// quiz sessions on >=2 distinct days.
const GMAT_MASTERY_ALPHA: f64 = 0.3;
const GMAT_QUIZ_MASTERY_ALPHA: f64 = 0.5;
const GMAT_QUIZ_PASS_ACCURACY: f64 = 0.85;
const GMAT_QUIZ_PASS_SESSIONS: usize = 2;
const GMAT_QUIZ_PASS_DISTINCT_DAYS: usize = 2;
// topic-quiz length + spacing before a passed-once topic is re-quizzed. 7 (not
// 6) so a single miss still clears the 85% bar: 6/7 = 85.7% >= 0.85, where
// 5/6 = 83.3% would fail.
const GMAT_QUIZ_N: i64 = 7;
const GMAT_QUIZ_RESPACE_SECS: i64 = 3 * 86_400;
// milestone checkpoint: default length, ceiling, and topics-learned gate
const GMAT_MILESTONE_N: i64 = 12;
const GMAT_MILESTONE_N_MAX: i64 = 25;
const GMAT_MILESTONE_MIN_TOPICS: i64 = 3;

/// Timing risk classification for one first-exposure attempt (Brainlift: wrong,
/// SLOW, or guessed questions are all future scheduled learning events):
/// - "rushed_wrong": wrong in under half the target pace (careless signal)
/// - "slow_correct": right but over 1.5x the target pace (fragile knowledge)
fn gmat_time_flag(ms: i64, correct: bool) -> Option<&'static str> {
    if ms <= 0 {
        return None; // untimed legacy rows carry no signal
    }
    if !correct && ms < GMAT_TARGET_MS / 2 {
        Some("rushed_wrong")
    } else if correct && ms > GMAT_TARGET_MS * 3 / 2 {
        Some("slow_correct")
    } else {
        None
    }
}

/// Transparent heuristic map: first-exposure accuracy -> GMAT Focus Quant
/// section score (60-90). Anchors: 0.40->70, 0.90->88. Mirrored nowhere else -
/// this is the single implementation both platforms and mocks use.
fn gmat_accuracy_to_quant(acc: f64) -> i64 {
    (70.0 + (acc - 0.40) * (88.0 - 70.0) / (0.90 - 0.40))
        .clamp(60.0, 90.0)
        .round() as i64
}

impl Collection {
    fn gmat_select_deck(&mut self, deck_name: &str) -> Result<()> {
        let native = crate::decks::NativeDeckName::from_human_name(deck_name);
        if let Some(did) = self.storage.get_deck_id(native.as_native_str())? {
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
    /// else Again), writing a revlog entry with the real time taken. This is a
    /// genuine review; `ms` feeds the timing analytics.
    pub fn gmat_mobile_answer(&mut self, card_id: i64, correct: bool, ms: u32) -> Result<()> {
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
            milliseconds_taken: ms.min(600_000),
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

        let target = self.gmat_target_retention();
        let memory = self.gmat_memory_json(now, target)?;
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

    /// Target retention for the GMAT deck (its FSRS `desiredRetention`), so
    /// Memory calibration matches whatever the scheduler is actually aiming for.
    /// Falls back to the FSRS default when the deck/config is missing.
    fn gmat_target_retention(&self) -> f64 {
        let native = crate::decks::NativeDeckName::from_human_name("GMAT::Quant");
        self.storage
            .get_deck_id(native.as_native_str())
            .ok()
            .flatten()
            .and_then(|did| self.storage.get_deck(did).ok().flatten())
            .and_then(|deck| deck.config_id())
            .and_then(|dcid| self.storage.get_deck_config(dcid).ok().flatten())
            .map(|conf| conf.inner.desired_retention as f64)
            .unwrap_or(TARGET_RETENTION)
    }

    fn gmat_memory_json(&self, now: i64, target: f64) -> Result<serde_json::Value> {
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
        let mut stmt = self.storage.db.prepare(
            "select cid, ease, time from revlog where lastIvl = 0 and ease between 1 and 4",
        )?;
        let raw: Vec<(i64, i64, i64)> = stmt
            .query_map([], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)))?
            .collect::<rusqlite::Result<_>>()?;
        // Unified application attempt: (split_key, ok, ms, topic). Revlog
        // first-exposure rows key by cid; the synced application log
        // (quiz/milestone answers, which never touch the scheduler) keys by ts.
        // Folding both in means Performance reflects the assessment layer while
        // the evidence-based honesty thresholds keep working identically.
        let mut timed: Vec<(i64, u8, i64, String)> = raw
            .into_iter()
            .filter(|(cid, _, _)| card_topics.contains_key(cid))
            .map(|(cid, ease, ms)| {
                let topic = card_topics.get(&cid).cloned().unwrap_or_default();
                (cid, u8::from(ease >= 2), ms, topic)
            })
            .collect();
        for a in self
            .get_config_optional::<Vec<Value>, _>("gmatApplication")
            .unwrap_or_default()
        {
            timed.push((
                a["ts"].as_i64().unwrap_or(0),
                u8::from(a["correct"].as_bool().unwrap_or(false)),
                a["ms"].as_i64().unwrap_or(0),
                a["topic"].as_str().unwrap_or("").to_string(),
            ));
        }
        let total = timed.len();
        if total < PERF_MIN_ATTEMPTS {
            return Ok(json!({
                "status": "abstain", "attempts": total,
                "attempts_required": PERF_MIN_ATTEMPTS,
                "reason": format!("Need {PERF_MIN_ATTEMPTS} new-question attempts; you have {total}."),
                "updated_ts": now,
            }));
        }
        let correct: usize = timed.iter().map(|(_, ok, _, _)| *ok as usize).sum();
        let acc = correct as f64 / total as f64;
        let se = (acc * (1.0 - acc) / total as f64).sqrt();

        // per-topic accuracy (only where >= PERF_MIN_PER_TOPIC)
        let mut per_topic: HashMap<&str, (usize, usize)> = HashMap::new();
        for (_, ok, _, topic) in &timed {
            let e = per_topic.entry(topic.as_str()).or_default();
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

        // held-out per-topic model vs global-mean baseline (Brier), split by key
        let train: Vec<&(i64, u8, i64, String)> =
            timed.iter().filter(|(k, _, _, _)| k % 10 < 7).collect();
        let test: Vec<&(i64, u8, i64, String)> =
            timed.iter().filter(|(k, _, _, _)| k % 10 >= 7).collect();
        let eval = if !train.is_empty() && !test.is_empty() {
            let g_mean =
                train.iter().map(|(_, ok, _, _)| *ok as f64).sum::<f64>() / train.len() as f64;
            let mut tt: HashMap<&str, (f64, f64)> = HashMap::new();
            for (_, ok, _, topic) in &train {
                let e = tt.entry(topic.as_str()).or_default();
                e.0 += *ok as f64;
                e.1 += 1.0;
            }
            let base = test
                .iter()
                .map(|(_, ok, _, _)| (g_mean - *ok as f64).powi(2))
                .sum::<f64>()
                / test.len() as f64;
            let model = test
                .iter()
                .map(|(_, ok, _, topic)| {
                    let pred = tt.get(topic.as_str()).map(|(c, n)| c / n).unwrap_or(g_mean);
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

        // Timing analytics over timed attempts: separates "fast but wrong"
        // (careless) from "slow but correct" (fragile).
        let with_time: Vec<&(i64, u8, i64, String)> =
            timed.iter().filter(|(_, _, ms, _)| *ms > 0).collect();
        let timing = if with_time.is_empty() {
            serde_json::Value::Null
        } else {
            let n = with_time.len();
            let avg_ms = with_time.iter().map(|(_, _, ms, _)| ms).sum::<i64>() / n as i64;
            let rushed_wrong = with_time
                .iter()
                .filter(|(_, ok, ms, _)| gmat_time_flag(*ms, *ok == 1) == Some("rushed_wrong"))
                .count();
            let slow_correct = with_time
                .iter()
                .filter(|(_, ok, ms, _)| gmat_time_flag(*ms, *ok == 1) == Some("slow_correct"))
                .count();
            json!({
                "n": n,
                "avg_ms": avg_ms,
                "target_ms": GMAT_TARGET_MS,
                "rushed_wrong": rushed_wrong,
                "slow_correct": slow_correct,
            })
        };

        Ok(json!({
            "status": "shown",
            "point": (acc * 100.0).round() as i64,
            "low": ((acc - 1.96 * se).max(0.0) * 100.0).round() as i64,
            "high": ((acc + 1.96 * se).min(1.0) * 100.0).round() as i64,
            "attempts": total,
            "weak_topics": weak,
            "eval": eval,
            "timing": timing,
            "updated_ts": now,
        }))
    }

    /// Mock-exam history stored by the desktop (config `gmatMocks`), scored
    /// here so the accuracy->Quant map has exactly one implementation.
    fn gmat_mock_history(&self) -> Vec<serde_json::Value> {
        self.get_config_optional::<Vec<serde_json::Value>, _>("gmatMocks")
            .unwrap_or_default()
            .iter()
            .filter_map(|m| {
                let acc = m.get("accuracy")?.as_f64()?;
                Some(json!({
                    "ts": m.get("ts").and_then(|v| v.as_i64()).unwrap_or(0),
                    "accuracy": acc,
                    "n": m.get("n").and_then(|v| v.as_i64()).unwrap_or(0),
                    "q": gmat_accuracy_to_quant(acc),
                }))
            })
            .collect()
    }

    /// Real official/practice-test Quant scores the user has logged (config
    /// `gmatOfficialScores`). These are the ground truth that calibrates the
    /// accuracy->Q projection (PRD Step 4 - validate against official scores).
    fn gmat_official_scores(&self) -> Vec<serde_json::Value> {
        self.get_config_optional::<Vec<serde_json::Value>, _>("gmatOfficialScores")
            .unwrap_or_default()
            .into_iter()
            .filter(|s| s.get("quant").and_then(|v| v.as_f64()).is_some())
            .collect()
    }

    /// Bias offset that calibrates the projection: the mean of
    /// (official Quant - what the app projected at the time that score was
    /// logged). Only entries carrying a numeric `projected_at_entry` count, so
    /// this compares like-for-like. Returns (bias, mean_abs_residual, n).
    fn gmat_calibration(&self, official: &[serde_json::Value]) -> Option<(f64, f64, usize)> {
        let paired: Vec<(f64, f64)> = official
            .iter()
            .filter_map(|s| {
                let q = s.get("quant")?.as_f64()?;
                let p = s.get("projected_at_entry")?.as_f64()?;
                Some((p, q))
            })
            .collect();
        if paired.is_empty() {
            return None;
        }
        let n = paired.len();
        let bias = paired.iter().map(|(p, q)| q - p).sum::<f64>() / n as f64;
        let residual = paired.iter().map(|(p, q)| (q - p).abs()).sum::<f64>() / n as f64;
        Some((bias, residual, n))
    }

    fn gmat_readiness_json(
        &self,
        memory: &serde_json::Value,
        performance: &serde_json::Value,
        coverage_pct: f64,
        now: i64,
    ) -> serde_json::Value {
        let mocks = self.gmat_mock_history();
        let official = self.gmat_official_scores();
        let calibration = self.gmat_calibration(&official);
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
                "mocks": mocks,
                "official": official,
                "updated_ts": now,
            });
        }
        let acc = performance["point"].as_f64().unwrap_or(0.0) / 100.0;
        let acc_low = performance["low"].as_f64().unwrap_or(0.0) / 100.0;
        let acc_high = performance["high"].as_f64().unwrap_or(0.0) / 100.0;
        let point = gmat_accuracy_to_quant(acc);
        let low = gmat_accuracy_to_quant(acc_low);
        let high = gmat_accuracy_to_quant(acc_high);
        // Calibration signal: how far the projection sits from the latest
        // timed mock. A large gap is displayed, not hidden (honesty rule).
        let mock_gap = mocks
            .last()
            .and_then(|m| m.get("q"))
            .and_then(|q| q.as_i64())
            .map(|q| point - q);

        // Calibration to real scores: shift the heuristic by the measured bias
        // and surface it as the headline, while keeping the raw map visible.
        let clampq = |v: f64| v.clamp(60.0, 90.0).round() as i64;
        let round1 = |v: f64| (v * 10.0).round() / 10.0;
        let (calibration_json, method, confidence) = match calibration {
            Some((bias, residual, n)) => {
                let cal = json!({
                    "n": n,
                    "bias": round1(bias),
                    "residual": round1(residual),
                    "point": clampq(point as f64 + bias),
                    "low": clampq(low as f64 + bias),
                    "high": clampq(high as f64 + bias),
                });
                let method = format!(
                    "Calibrated to your {n} official score(s): the accuracy->Q map is shifted by {:+.0} point(s) (mean error {:.1}).",
                    round1(bias),
                    round1(residual),
                );
                // Real outcomes are stronger evidence than coverage alone.
                let confidence = if n >= 2 {
                    if coverage_pct >= 80.0 { "high" } else { "medium" }
                } else if coverage_pct >= 80.0 && attempts >= 150 {
                    "medium"
                } else {
                    "low"
                };
                (cal, method, confidence)
            }
            None => (
                serde_json::Value::Null,
                "Heuristic map from held-out first-exposure accuracy; not yet validated against official practice-test scores.".to_string(),
                if coverage_pct >= 80.0 && attempts >= 150 { "medium" } else { "low" },
            ),
        };
        json!({
            "status": "shown",
            "section": "Quant",
            "point": point,
            "low": low,
            "high": high,
            "scale": "GMAT Focus Quant section (60-90)",
            "confidence": confidence,
            "method": method,
            "total_status": "abstain",
            "total_reason": "Total (205-805) needs Verbal + Data Insights data (not yet in scope).",
            "mocks": mocks,
            "mock_gap": mock_gap,
            "official": official,
            "calibration": calibration_json,
            "updated_ts": now,
        })
    }
}

// ---------------------------------------------------------------------------
// GMATWiz endpoint dispatch (iOS parity with qt/aqt/mediasrv.py `gmat_*`).
//
// The SvelteKit UI POSTs to /_anki/<method>; on desktop Python answers, on iOS
// this Rust dispatch does. Every arm mirrors the matching Python handler's
// behavior and JSON shape, since the SAME UI + ts/routes/gmat/api.ts types
// consume both. Reads that Python takes from the collection are taken from the
// collection here too; lessons/content come from the bundled `resource_dir`.
// ---------------------------------------------------------------------------

/// Read one field by name from a note's (field_names, field_values) pair.
fn field_value(names: &[String], vals: &[String], name: &str) -> String {
    names
        .iter()
        .position(|n| n == name)
        .and_then(|i| vals.get(i))
        .cloned()
        .unwrap_or_default()
}

/// Parse a POST body that may be empty (mirrors `json.loads(data or b"{}")`).
fn parse_body(body: &str) -> Value {
    if body.trim().is_empty() {
        json!({})
    } else {
        serde_json::from_str(body).unwrap_or_else(|_| json!({}))
    }
}

/// Read an integer from JSON (accepting ints or floats), else `default`.
fn json_i64(v: &Value, default: i64) -> i64 {
    v.as_i64()
        .or_else(|| v.as_f64().map(|f| f as i64))
        .unwrap_or(default)
}

/// Read an optional integer from JSON (None for missing/null/non-numeric),
/// mirroring the Python `opt_int` helper for official-score fields.
fn json_opt_i64(v: &Value) -> Option<i64> {
    v.as_i64().or_else(|| v.as_f64().map(|f| f as i64))
}

/// weak/developing/strong bucket for a mastery value (mirrors `_gmat_status`).
fn gmat_status_str(mastery: f64) -> &'static str {
    if mastery < 0.5 {
        "weak"
    } else if mastery < 0.8 {
        "developing"
    } else {
        "strong"
    }
}

/// Per-topic mastery bar derived from the target GMAT Focus total (mirrors
/// `_gmat_mastery_bar`). Higher goals demand deeper mastery before a topic's done.
fn gmat_mastery_bar(target_score: i64) -> f64 {
    if target_score >= 705 {
        0.90
    } else if target_score >= 645 {
        0.85
    } else if target_score >= 585 {
        0.80
    } else {
        0.72
    }
}

/// Round half-to-even like Python's built-in `round`, so pacing/session numbers
/// match the desktop exactly at .5 boundaries.
fn py_round(x: f64) -> i64 {
    let floor = x.floor();
    if (x - floor - 0.5).abs() < 1e-9 {
        let f = floor as i64;
        if f.rem_euclid(2) == 0 {
            f
        } else {
            f + 1
        }
    } else {
        x.round() as i64
    }
}

/// Round to 2 decimals half-to-even (Python `round(x, 2)`).
fn py_round2(x: f64) -> f64 {
    py_round(x * 100.0) as f64 / 100.0
}

/// Days from today (local) to a `YYYY-MM-DD` exam date, or None if unparseable.
fn gmat_days_to_exam(exam_date: &str) -> Option<i64> {
    if exam_date.is_empty() {
        return None;
    }
    let exam = NaiveDate::parse_from_str(exam_date, "%Y-%m-%d").ok()?;
    Some((exam - Local::now().date_naive()).num_days())
}

/// Nominal spaced-review minutes for a projected study day (mirrors
/// `_gmat_cal_review_min`): grows with topics learned, reusing the Today
/// per-review cost (1.5 min/card, ~3 due cards per learned topic, capped at 30).
fn gmat_cal_review_min(learned: i64) -> i64 {
    let nominal_due = (3 * learned + 2).min(30);
    py_round(1.5 * nominal_due as f64)
}

/// Title-cased leaf of an "a::b::leaf_name" topic id (mirrors `topic_leaf`).
fn topic_leaf(topic: &str) -> String {
    let leaf = topic.rsplit("::").next().unwrap_or("");
    if leaf.is_empty() {
        return "your weak topic".to_string();
    }
    leaf.replace('_', " ")
        .split(' ')
        .map(|word| {
            let mut chars = word.chars();
            match chars.next() {
                Some(first) => {
                    first.to_uppercase().collect::<String>() + &chars.as_str().to_lowercase()
                }
                None => String::new(),
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

/// One score card in the "temporarily unavailable" state (mirrors
/// `_score_unavailable`).
fn gmat_score_unavailable(now: i64) -> Value {
    json!({
        "status": "abstain",
        "reason": "Scores are temporarily unavailable.",
        "updated_ts": now,
    })
}

/// Whole-scores fallback when the engine call fails (mirrors the `_gmat_scores`
/// degrade path so reviews keep working even if scoring hiccups).
fn gmat_scores_fallback(now: i64) -> Value {
    json!({
        "memory": gmat_score_unavailable(now),
        "performance": gmat_score_unavailable(now),
        "readiness": gmat_score_unavailable(now),
        "topics_covered": 0,
        "topics_total": 18,
    })
}

/// Bundled lesson catalog (`resource_dir/lessons/index.json`), or empty catalog.
fn gmat_read_lessons_index(resource_dir: &str) -> Value {
    let path = std::path::Path::new(resource_dir)
        .join("lessons")
        .join("index.json");
    std::fs::read_to_string(path)
        .ok()
        .and_then(|t| serde_json::from_str::<Value>(&t).ok())
        .unwrap_or_else(|| json!({ "topics": [] }))
}

/// The authored lesson for `topic_id`, read from the bundled lessons folder
/// (mirrors `_load_lesson_by_topic`). None if the topic/file is missing.
fn gmat_read_lesson_by_topic(resource_dir: &str, topic_id: &str) -> Option<Value> {
    let index = gmat_read_lessons_index(resource_dir);
    let topics = index["topics"].as_array()?;
    let mut json_name: Option<String> = None;
    for t in topics {
        if t["topic_id"].as_str() == Some(topic_id) {
            json_name = t["json"]
                .as_str()
                .filter(|s| !s.is_empty())
                .map(String::from)
                .or_else(|| Some(format!("{}.json", t["slug"].as_str().unwrap_or(""))));
            break;
        }
    }
    let name = json_name?;
    let path = std::path::Path::new(resource_dir).join("lessons").join(name);
    std::fs::read_to_string(path)
        .ok()
        .and_then(|t| serde_json::from_str::<Value>(&t).ok())
}

/// Bundled practice-test catalog (`resource_dir/tests/index.json`), or empty.
fn gmat_read_tests_index(resource_dir: &str) -> Value {
    let path = std::path::Path::new(resource_dir)
        .join("tests")
        .join("index.json");
    std::fs::read_to_string(path)
        .ok()
        .and_then(|t| serde_json::from_str::<Value>(&t).ok())
        .unwrap_or_else(|| json!({ "years": {} }))
}

/// A form's `year` as a string: its own `year` field (string or number),
/// falling back to the `years` map key it was listed under.
fn gmat_form_year(form: &Value, group_key: &str) -> String {
    form["year"]
        .as_str()
        .map(String::from)
        .or_else(|| form["year"].as_i64().map(|n| n.to_string()))
        .unwrap_or_else(|| group_key.to_string())
}

/// The authored practice-test form for `form_id`, read from the bundled tests
/// folder (`tests/<year>/<id>.json`); the year is resolved from the index so the
/// caller only needs the id. None if the form/file is missing.
fn gmat_read_test_form(resource_dir: &str, form_id: &str) -> Option<Value> {
    if form_id.is_empty() {
        return None;
    }
    let index = gmat_read_tests_index(resource_dir);
    let years = index["years"].as_object()?;
    let mut year: Option<String> = None;
    for (group_key, forms) in years {
        if let Some(arr) = forms.as_array() {
            for f in arr {
                if f["id"].as_str() == Some(form_id) {
                    year = Some(gmat_form_year(f, group_key));
                    break;
                }
            }
        }
        if year.is_some() {
            break;
        }
    }
    let year = year?;
    let path = std::path::Path::new(resource_dir)
        .join("tests")
        .join(year)
        .join(format!("{form_id}.json"));
    std::fs::read_to_string(path)
        .ok()
        .and_then(|t| serde_json::from_str::<Value>(&t).ok())
}

/// Bundled question content (`resource_dir/content/{seed,questions}.json`),
/// used only as a fallback when the collection has no GMAT PS notes yet (fresh
/// phone), so the practice/pretest/mock screens still render.
fn gmat_read_seed_notes(resource_dir: &str) -> Vec<GmatNoteFields> {
    let mut out = Vec::new();
    for name in ["seed.json", "questions.json"] {
        let path = std::path::Path::new(resource_dir).join("content").join(name);
        let Ok(text) = std::fs::read_to_string(&path) else {
            continue;
        };
        let Ok(data) = serde_json::from_str::<Value>(&text) else {
            continue;
        };
        let items = if data.is_array() {
            data.as_array().cloned().unwrap_or_default()
        } else {
            data["questions"].as_array().cloned().unwrap_or_default()
        };
        for q in items {
            let opts = &q["options"];
            out.push(GmatNoteFields {
                nid: 0,
                stem: q["stem"].as_str().unwrap_or("").to_string(),
                option_a: opts["A"].as_str().unwrap_or("").to_string(),
                option_b: opts["B"].as_str().unwrap_or("").to_string(),
                option_c: opts["C"].as_str().unwrap_or("").to_string(),
                option_d: opts["D"].as_str().unwrap_or("").to_string(),
                option_e: opts["E"].as_str().unwrap_or("").to_string(),
                correct: q["correct"].as_str().unwrap_or("").to_string(),
                explanation: q["explanation"].as_str().unwrap_or("").to_string(),
                topic: q["topic"].as_str().unwrap_or("").to_string(),
                difficulty: q["difficulty"].as_str().unwrap_or("").to_string(),
            });
        }
    }
    out
}

/// A GMAT PS question's fields, sourced from a collection note or bundled seed.
struct GmatNoteFields {
    nid: i64,
    stem: String,
    option_a: String,
    option_b: String,
    option_c: String,
    option_d: String,
    option_e: String,
    correct: String,
    explanation: String,
    topic: String,
    difficulty: String,
}

impl GmatNoteFields {
    fn options(&self) -> Value {
        json!({
            "A": self.option_a,
            "B": self.option_b,
            "C": self.option_c,
            "D": self.option_d,
            "E": self.option_e,
        })
    }

    /// Shape for `GmatQuestion` (gmatQuestions).
    fn question_json(&self) -> Value {
        json!({
            "stem": self.stem,
            "options": self.options(),
            "correct": self.correct,
            "explanation": self.explanation,
            "topic": self.topic,
            "difficulty": self.difficulty,
        })
    }

    /// Shape for `PretestQuestion` (gmatPretestQuestions).
    fn pretest_json(&self) -> Value {
        json!({
            "stem": self.stem,
            "options": self.options(),
            "correct": self.correct,
            "topic": self.topic,
            "difficulty": self.difficulty,
        })
    }

    /// Shape for `MockQuestion` (gmatMockQuestions); difficulty defaults to
    /// "medium" to match the desktop handler.
    fn mock_json(&self, seen: bool) -> Value {
        let difficulty = if self.difficulty.is_empty() {
            "medium".to_string()
        } else {
            self.difficulty.clone()
        };
        json!({
            "stem": self.stem,
            "options": self.options(),
            "correct": self.correct,
            "topic": self.topic,
            "difficulty": difficulty,
            "seen": seen,
        })
    }
}

impl Collection {
    /// Count cards matching an Anki search (0 on error, like Python's `count`).
    fn gmat_count(&mut self, search: &str) -> usize {
        self.search_cards(search, SortMode::NoOrder)
            .map(|c| c.len())
            .unwrap_or(0)
    }

    /// Persist one JSON config value (non-undoable), mirroring `col.set_config`.
    fn gmat_put_config(&mut self, key: &str, val: &Value) -> Result<()> {
        self.set_config_json(key, val, false)?;
        Ok(())
    }

    /// Every GMAT PS note in the collection, as question field structs.
    fn gmat_notes_from_collection(&mut self) -> Result<Vec<GmatNoteFields>> {
        let nids = self.search_notes("note:\"GMAT PS\"", SortMode::NoOrder)?;
        let mut out = Vec::with_capacity(nids.len());
        for nid in nids {
            let Some(note) = self.storage.get_note(nid)? else {
                continue;
            };
            let names = self.storage.get_field_names(note.notetype_id)?;
            let vals = note.fields();
            out.push(GmatNoteFields {
                nid: nid.0,
                stem: field_value(&names, vals, "Stem"),
                option_a: field_value(&names, vals, "OptionA"),
                option_b: field_value(&names, vals, "OptionB"),
                option_c: field_value(&names, vals, "OptionC"),
                option_d: field_value(&names, vals, "OptionD"),
                option_e: field_value(&names, vals, "OptionE"),
                correct: field_value(&names, vals, "Correct"),
                explanation: field_value(&names, vals, "Explanation"),
                topic: field_value(&names, vals, "Topic"),
                difficulty: field_value(&names, vals, "Difficulty"),
            });
        }
        Ok(out)
    }

    /// The question pool: the collection's GMAT PS notes, or - if the collection
    /// has not been seeded yet - the bundled content files (see
    /// `gmat_read_seed_notes`).
    fn gmat_question_pool(&mut self, resource_dir: &str) -> Result<Vec<GmatNoteFields>> {
        let from_col = self.gmat_notes_from_collection()?;
        if from_col.is_empty() {
            Ok(gmat_read_seed_notes(resource_dir))
        } else {
            Ok(from_col)
        }
    }

    /// Distinct non-empty topics present in the pool, in first-seen order
    /// (mirrors `_gmat_notes_by_topic().keys()`).
    fn gmat_pool_topics(&mut self, resource_dir: &str) -> Result<Vec<String>> {
        let pool = self.gmat_question_pool(resource_dir)?;
        let mut seen = HashSet::new();
        let mut topics = Vec::new();
        for q in &pool {
            if !q.topic.is_empty() && seen.insert(q.topic.clone()) {
                topics.push(q.topic.clone());
            }
        }
        Ok(topics)
    }

    /// Topic field of a card's note ("" if missing), mirrors `_gmat_topic_of_card`.
    fn gmat_topic_of_card(&mut self, card_id: i64) -> Result<String> {
        let Some(card) = self.storage.get_card(CardId(card_id))? else {
            return Ok(String::new());
        };
        let Some(note) = self.storage.get_note(card.note_id())? else {
            return Ok(String::new());
        };
        let names = self.storage.get_field_names(note.notetype_id)?;
        Ok(field_value(&names, note.fields(), "Topic"))
    }

    /// The app's current RAW Quant projection (mirrors `_gmat_current_projection`).
    fn gmat_current_projection(&mut self) -> Option<i64> {
        let scores: Value = serde_json::from_str(&self.gmat_scores_json().ok()?).ok()?;
        if scores["readiness"]["status"].as_str() == Some("shown") {
            scores["readiness"]["point"].as_i64()
        } else {
            None
        }
    }

    /// EMA-update one topic's mastery from a single answer and keep the stored
    /// plan + topic-aware scheduling in sync. No-op until a plan exists. Mirrors
    /// `_gmat_update_mastery`. `alpha` is the EMA weight (0.3 for ordinary
    /// drills, 0.5 for deliberate quiz/milestone answers); this drives the plan
    /// display + topic-aware order, while the hard mastery GATE is quiz-history
    /// based (see `gmat_topic_mastered`).
    fn gmat_update_mastery(&mut self, topic: &str, correct: bool, alpha: f64) -> Result<()> {
        if topic.is_empty() {
            return Ok(());
        }
        let plan_val = self.get_config_optional::<Value, _>("gmatPlan");
        let has_plan = plan_val.as_ref().map(|p| !p.is_null()).unwrap_or(false);
        if !has_plan {
            return Ok(());
        }
        let mut plan = plan_val.unwrap();

        let mut diagnosis = self
            .get_config_optional::<Value, _>("gmatDiagnosis")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let old = diagnosis.get(topic).and_then(|v| v.as_f64()).unwrap_or(0.5);
        let target = if correct { 1.0 } else { 0.0 };
        let new = (((1.0 - alpha) * old + alpha * target) * 1000.0).round() / 1000.0;
        diagnosis
            .as_object_mut()
            .unwrap()
            .insert(topic.to_string(), json!(new));
        self.gmat_put_config("gmatDiagnosis", &diagnosis)?;

        // best-effort, exactly like the desktop try/except around the RPC
        let _ = self.set_topic_mastery(topic, new as f32);

        if plan.is_object() {
            if let Some(topics_ref) = plan.get("topics").and_then(|v| v.as_array()) {
                let mut topics = topics_ref.clone();
                let status = gmat_status_str(new);
                let mut found = false;
                for entry in topics.iter_mut() {
                    if entry.get("topic").and_then(|v| v.as_str()) == Some(topic) {
                        if let Some(obj) = entry.as_object_mut() {
                            obj.insert("mastery".to_string(), json!(new));
                            obj.insert("status".to_string(), json!(status));
                        }
                        found = true;
                        break;
                    }
                }
                if !found {
                    topics.push(json!({
                        "topic": topic,
                        "mastery": new,
                        "status": status,
                    }));
                }
                topics.sort_by(|a, b| {
                    let ma = a.get("mastery").and_then(|v| v.as_f64()).unwrap_or(0.5);
                    let mb = b.get("mastery").and_then(|v| v.as_f64()).unwrap_or(0.5);
                    ma.partial_cmp(&mb).unwrap_or(std::cmp::Ordering::Equal)
                });
                plan.as_object_mut()
                    .unwrap()
                    .insert("topics".to_string(), Value::Array(topics));
                self.gmat_put_config("gmatPlan", &plan)?;
            }
        }
        Ok(())
    }

    /// Absolute day index from the scheduler day cutoff - constant within an
    /// Anki day, +1 each rollover (mirrors `_gmat_day_bucket`). Used to stamp
    /// quiz sessions so the mastery gate can require DISTINCT days.
    fn gmat_day_bucket(&mut self) -> i64 {
        self.timing_today()
            .map(|t| t.next_day_at.0 / 86_400)
            .unwrap_or_else(|_| TimestampMillis::now().0 / 1000 / 86_400)
    }

    /// The SOFT mastery gate (mirrors `_gmat_topic_mastered`): True once the
    /// topic's quiz history has >= GMAT_QUIZ_PASS_SESSIONS passing sessions
    /// (accuracy >= the pass bar) over >= GMAT_QUIZ_PASS_DISTINCT_DAYS distinct
    /// days. This is the single definition of "mastered" pacing + Today + Study
    /// read; the EMA diagnosis value is only the display/scheduling signal.
    fn gmat_topic_mastered(&self, topic: &str) -> bool {
        if topic.is_empty() {
            return false;
        }
        let quizzes = self
            .get_config_optional::<Value, _>("gmatQuizzes")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let sessions = match quizzes.get(topic).and_then(|v| v.as_array()) {
            Some(s) => s,
            None => return false,
        };
        let passing: Vec<&Value> = sessions
            .iter()
            .filter(|s| s["accuracy"].as_f64().unwrap_or(0.0) >= GMAT_QUIZ_PASS_ACCURACY)
            .collect();
        if passing.len() < GMAT_QUIZ_PASS_SESSIONS {
            return false;
        }
        let distinct_days: HashSet<i64> = passing
            .iter()
            .map(|s| s["day"].as_i64().unwrap_or(0))
            .collect();
        distinct_days.len() >= GMAT_QUIZ_PASS_DISTINCT_DAYS
    }

    /// Log one assessment answer as an APPLICATION attempt (mirrors
    /// `_gmat_record_application`). Quiz/milestone answers never touch the
    /// scheduler/revlog, so the Performance reader folds this synced log in.
    fn gmat_record_application(&mut self, topic: &str, correct: bool, ms: i64, now: i64) -> Result<()> {
        let mut log = self
            .get_config_optional::<Vec<Value>, _>("gmatApplication")
            .unwrap_or_default();
        log.push(json!({
            "ts": now,
            "topic": topic,
            "correct": correct,
            "ms": ms,
        }));
        let start = log.len().saturating_sub(2000);
        let trimmed = log[start..].to_vec();
        self.gmat_put_config("gmatApplication", &Value::Array(trimmed))
    }

    /// Turn a classified miss into scheduled remediation (mirrors
    /// `_gmat_apply_repair`). NOTE: the concept-gap lesson-item import
    /// (`_schedule_lesson_items`) is not ported on mobile (no notetype importer
    /// in rslib yet); the mastery penalty + repair/drill queueing still happen,
    /// matching the desktop's try/except fallback when scheduling fails.
    fn gmat_apply_repair(&mut self, topic: &str, why: &str) -> Result<()> {
        if topic.is_empty() {
            return Ok(());
        }
        let now = TimestampMillis::now().0 / 1000;
        match why {
            "concept_gap" => {
                self.gmat_update_mastery(topic, false, GMAT_MASTERY_ALPHA)?;
                let mut repairs = self
                    .get_config_optional::<Value, _>("gmatRepairTopics")
                    .filter(Value::is_object)
                    .unwrap_or_else(|| json!({}));
                repairs
                    .as_object_mut()
                    .unwrap()
                    .insert(topic.to_string(), json!(now));
                self.gmat_put_config("gmatRepairTopics", &repairs)?;
            }
            "timing" => {
                let mut drills = self
                    .get_config_optional::<Value, _>("gmatTimedDrill")
                    .filter(Value::is_object)
                    .unwrap_or_else(|| json!({}));
                drills
                    .as_object_mut()
                    .unwrap()
                    .insert(topic.to_string(), json!(now));
                self.gmat_put_config("gmatTimedDrill", &drills)?;
            }
            "guess" => {
                self.gmat_update_mastery(topic, false, GMAT_MASTERY_ALPHA)?;
            }
            _ => {}
        }
        Ok(())
    }

    /// Dated pacing + on/behind-track status (mirrors `_gmat_pacing`).
    fn gmat_pacing(&self) -> Value {
        let plan = self
            .get_config_optional::<Value, _>("gmatPlan")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let profile = self
            .get_config_optional::<Value, _>("gmatProfile")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));

        let empty: Vec<Value> = Vec::new();
        let topics = plan["topics"].as_array().unwrap_or(&empty);
        let topic_ids: HashSet<String> = topics
            .iter()
            .filter_map(|t| t["topic"].as_str().map(String::from))
            .collect();
        let topics_total = topics.len() as i64;
        // "Learned" now means MASTERED (passed the topic-quiz gate), NOT merely
        // lesson-done: a finished lesson without passing quizzes is still in
        // progress and counts toward remaining.
        let topics_learned = topic_ids
            .iter()
            .filter(|t| !t.is_empty() && self.gmat_topic_mastered(t))
            .count() as i64;
        let topics_remaining = (topics_total - topics_learned).max(0);
        let days_per_week = {
            let d = plan
                .get("days_per_week")
                .and_then(|v| v.as_i64())
                .or_else(|| profile.get("days_per_week").and_then(|v| v.as_i64()))
                .unwrap_or(5);
            if d == 0 {
                5
            } else {
                d
            }
        };

        let mut out = json!({
            "status": "no_pacing",
            "days_to_exam": Value::Null,
            "topics_total": topics_total,
            "topics_learned": topics_learned,
            "topics_remaining": topics_remaining,
            "behind_by": 0,
            "topics_per_study_day": 0.0,
            "study_days_remaining": Value::Null,
            "late_start": false,
        });

        let exam_date = profile["exam_date"].as_str().unwrap_or("");
        if topics_total == 0 || exam_date.is_empty() {
            return out;
        }
        let Ok(exam) = NaiveDate::parse_from_str(exam_date, "%Y-%m-%d") else {
            return out;
        };
        let today = Local::now().date_naive();
        let days_to_exam = (exam - today).num_days();
        out["days_to_exam"] = json!(days_to_exam);
        let study_days_remaining =
            py_round(days_to_exam.max(0) as f64 * days_per_week as f64 / 7.0).max(0);
        out["study_days_remaining"] = json!(study_days_remaining);

        if topics_remaining == 0 {
            out["status"] = json!("learning_complete");
            return out;
        }

        // HARD BOUNDARY: finish every lesson >= 10 calendar days before the exam.
        let learn_calendar_days = (days_to_exam - 10).max(0);
        let mut learn_days_remaining =
            py_round(learn_calendar_days as f64 * days_per_week as f64 / 7.0);
        if topics_remaining > 0 && learn_calendar_days > 0 {
            learn_days_remaining = learn_days_remaining.max(1);
        }

        // LATE-START EXCEPTION: already inside the final 10 days, or the learn
        // window is too tight to fit remaining topics at a sane pace (~<=2 topics/
        // study day) -> pace across ALL remaining study days so lessons still fit.
        let mut late_start = false;
        if learn_calendar_days <= 0
            || (learn_days_remaining > 0
                && topics_remaining as f64 / learn_days_remaining as f64 > 2.0)
        {
            late_start = true;
            learn_days_remaining = study_days_remaining;
            if topics_remaining > 0 && days_to_exam > 0 {
                learn_days_remaining = learn_days_remaining.max(1);
            }
        }
        out["late_start"] = json!(late_start);

        let topics_per_study_day = if learn_days_remaining != 0 {
            py_round2(topics_remaining as f64 / learn_days_remaining as f64)
        } else {
            topics_remaining as f64
        };
        out["topics_per_study_day"] = json!(topics_per_study_day);

        // expected progress by today: linear from plan creation to the exam-minus
        // -10 deadline (the hard lessons-finish-by date).
        let mut behind = 0i64;
        if let Some(created_ts) = plan.get("created_ts").and_then(|v| v.as_i64()) {
            if let Some(created) = Local
                .timestamp_opt(created_ts, 0)
                .single()
                .map(|dt| dt.date_naive())
            {
                let total_days = ((exam - created).num_days() - 10).max(1);
                let elapsed = (today - created).num_days().max(0);
                let frac = (elapsed as f64 / total_days as f64).min(1.0);
                let expected_learned = py_round(topics_total as f64 * frac);
                behind = (expected_learned - topics_learned).max(0);
            }
        }
        out["behind_by"] = json!(behind);
        out["status"] = json!(if behind > 0 { "behind" } else { "on_track" });
        out
    }

    /// A focused, GMAT-scoped activity summary (mirrors `gmat_stats`). Uses the
    /// scheduler day-cutoff (`timing_today().next_day_at`) as the desktop's
    /// `col.sched.day_cutoff`, and scopes revlog stats to the GMAT PS notetype.
    fn gmat_stats_json(&mut self) -> Result<String> {
        let base = "note:\"GMAT PS\"";
        let Some(nt) = self.get_notetype_by_name("GMAT PS")? else {
            return Ok(json!({ "has_data": false }).to_string());
        };
        let mid = nt.id.0;
        let cutoff = self.timing_today()?.next_day_at.0;
        let start_today = (cutoff - 86_400) * 1000;
        let scope = "cid in (select id from cards where nid in (select id from notes where mid=?))";

        let reviews_today: i64 = self.storage.db.query_row(
            &format!("select count() from revlog where id>=? and {scope}"),
            params![start_today, mid],
            |r| r.get(0),
        )?;
        let time_today_ms: i64 = self.storage.db.query_row(
            &format!("select coalesce(sum(time),0) from revlog where id>=? and {scope}"),
            params![start_today, mid],
            |r| r.get(0),
        )?;
        let reviews_total: i64 = self.storage.db.query_row(
            &format!("select count() from revlog where {scope}"),
            params![mid],
            |r| r.get(0),
        )?;

        // study streak: consecutive days (ending today or yesterday) with a review
        let day_indices: HashSet<i64> = {
            let mut stmt = self.storage.db.prepare(&format!(
                "select distinct cast((?-id/1000)/86400 as int) from revlog where {scope}"
            ))?;
            let rows = stmt.query_map(params![cutoff, mid], |r| r.get::<_, i64>(0))?;
            let mut set = HashSet::new();
            for row in rows {
                set.insert(row?);
            }
            set
        };
        let mut streak = 0i64;
        let mut i = if day_indices.contains(&0) { 0 } else { 1 };
        while day_indices.contains(&i) {
            streak += 1;
            i += 1;
        }

        // 7-day review sparkline (6 days ago .. today)
        let mut spark: Vec<i64> = Vec::new();
        for d in (0i64..7).rev() {
            let s = (cutoff - (d + 1) * 86_400) * 1000;
            let e = (cutoff - d * 86_400) * 1000;
            let count: i64 = self.storage.db.query_row(
                &format!("select count() from revlog where id>=? and id<? and {scope}"),
                params![s, e, mid],
                |r| r.get(0),
            )?;
            spark.push(count);
        }
        let forecast: Vec<usize> = (0..7)
            .map(|d| self.gmat_count(&format!("{base} -is:suspended prop:due={d}")))
            .collect();

        let due_today = self.gmat_count(&format!("{base} is:due"));
        let pipe_new = self.gmat_count(&format!("{base} is:new"));
        let pipe_learning = self.gmat_count(&format!("{base} is:learn"));
        let pipe_young =
            self.gmat_count(&format!("{base} -is:new -is:suspended prop:ivl>=1 prop:ivl<21"));
        let pipe_mature = self.gmat_count(&format!("{base} prop:ivl>=21"));
        let pipe_total = self.gmat_count(base);

        Ok(json!({
            "has_data": true,
            "reviews_today": reviews_today,
            "time_today_min": py_round(time_today_ms as f64 / 60_000.0),
            "reviews_total": reviews_total,
            "streak": streak,
            "due_today": due_today,
            "forecast": forecast,
            "spark": spark,
            "pipeline": {
                "new": pipe_new,
                "learning": pipe_learning,
                "young": pipe_young,
                "mature": pipe_mature,
                "total": pipe_total,
            },
        })
        .to_string())
    }

    /// Turn diagnostic results into per-topic mastery + a study plan (mirrors
    /// `gmat_submit_pretest`).
    fn gmat_submit_pretest(&mut self, body: &Value, resource_dir: &str, now: i64) -> Result<String> {
        let results = body["results"].as_array().cloned().unwrap_or_default();
        let mut agg: HashMap<String, (i64, i64)> = HashMap::new();
        for r in &results {
            let topic = r["topic"].as_str().unwrap_or("");
            if topic.is_empty() {
                continue;
            }
            let e = agg.entry(topic.to_string()).or_insert((0, 0));
            e.1 += 1;
            if r["correct"].as_bool().unwrap_or(false) {
                e.0 += 1;
            }
        }

        let topics = self.gmat_pool_topics(resource_dir)?;
        let mut diagnosis = serde_json::Map::new();
        for topic in &topics {
            let (correct, total) = agg.get(topic).copied().unwrap_or((0, 0));
            let mastery = if total > 0 {
                correct as f64 / total as f64
            } else {
                0.5
            };
            let rounded = (mastery * 1000.0).round() / 1000.0;
            diagnosis.insert(topic.clone(), json!(rounded));
            // best-effort RPC (matches desktop try/except)
            let _ = self.set_topic_mastery(topic, mastery as f32);
        }

        // now that mastery is populated, turn on topic-aware scheduling
        self.set_config_bool(BoolKey::TopicAwareScheduling, true, false)?;

        let profile = self
            .get_config_optional::<Value, _>("gmatProfile")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let days_to_exam = gmat_days_to_exam(profile["exam_date"].as_str().unwrap_or(""));
        let target_score = {
            let t = json_i64(&profile["target_score"], 645);
            let t = if t == 0 { 645 } else { t };
            t.clamp(205, 805)
        };
        let days_per_week = {
            let d = json_i64(&profile["days_per_week"], 5);
            if d == 0 {
                5
            } else {
                d
            }
        };

        // rank weakest-first; ties keep collection topic order (stable sort)
        let mut ranked: Vec<(String, f64)> = topics
            .iter()
            .map(|t| {
                let m = diagnosis.get(t.as_str()).and_then(|v| v.as_f64()).unwrap_or(0.5);
                (t.clone(), m)
            })
            .collect();
        ranked.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
        let plan_topics: Vec<Value> = ranked
            .iter()
            .map(|(t, m)| {
                json!({
                    "topic": t,
                    "mastery": m,
                    "status": gmat_status_str(*m),
                })
            })
            .collect();
        let plan = json!({
            "topics": plan_topics,
            "days_per_week": days_per_week,
            "days_to_exam": days_to_exam,
            "created_ts": now,
            "target_score": target_score,
            "mastery_bar": gmat_mastery_bar(target_score),
        });
        let diagnosis_val = Value::Object(diagnosis);
        self.gmat_put_config("gmatDiagnosis", &diagnosis_val)?;
        self.gmat_put_config("gmatPlan", &plan)?;
        Ok(json!({ "diagnosis": diagnosis_val, "plan": plan }).to_string())
    }

    /// The lesson catalog merged with the student's mastery + learned state
    /// (mirrors `gmat_lessons_index`).
    fn gmat_lessons_index_json(&mut self, resource_dir: &str) -> String {
        let index = gmat_read_lessons_index(resource_dir);
        let plan = self
            .get_config_optional::<Value, _>("gmatPlan")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let learned = self
            .get_config_optional::<Value, _>("gmatLearned")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let mut mastery_by: HashMap<String, Value> = HashMap::new();
        let mut status_by: HashMap<String, Value> = HashMap::new();
        if let Some(ts) = plan["topics"].as_array() {
            for t in ts {
                if let Some(tid) = t["topic"].as_str() {
                    mastery_by.insert(tid.to_string(), t["mastery"].clone());
                    status_by.insert(tid.to_string(), t["status"].clone());
                }
            }
        }
        let learned_obj = learned.as_object();
        let mut topics: Vec<Value> = Vec::new();
        if let Some(idx_topics) = index["topics"].as_array() {
            for t in idx_topics {
                let tid = t["topic_id"].as_str().unwrap_or("");
                topics.push(json!({
                    "topic_id": tid,
                    "title": t["title"].as_str().unwrap_or(""),
                    "domain": t["domain"].as_str().unwrap_or(""),
                    "mastery": mastery_by.get(tid).cloned().unwrap_or(Value::Null),
                    "status": status_by.get(tid).cloned().unwrap_or(Value::Null),
                    "learned": learned_obj.map(|o| o.contains_key(tid)).unwrap_or(false),
                    // the soft quiz gate (Study shows a pill + gates the quiz)
                    "mastered": self.gmat_topic_mastered(tid),
                }));
            }
        }
        // weakest first; unknown mastery (no diagnostic yet) goes last
        topics.sort_by(|a, b| {
            let an = a["mastery"].is_null();
            let bn = b["mastery"].is_null();
            let ak = if an { 1.0 } else { a["mastery"].as_f64().unwrap_or(1.0) };
            let bk = if bn { 1.0 } else { b["mastery"].as_f64().unwrap_or(1.0) };
            an.cmp(&bn)
                .then(ak.partial_cmp(&bk).unwrap_or(std::cmp::Ordering::Equal))
        });
        json!({ "topics": topics }).to_string()
    }

    /// Assemble today's session (mirrors `_gmat_build_today`).
    /// The next practice-test form the student hasn't taken yet (lowest id), as
    /// `{ id, year, label }`, or None if every form is taken / none exist.
    fn gmat_next_untaken_test(&self, resource_dir: &str) -> Option<Value> {
        let index = gmat_read_tests_index(resource_dir);
        let taken = self
            .get_config_optional::<Value, _>("gmatTestsTaken")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let taken_obj = taken.as_object();
        let mut forms: Vec<(String, String, String)> = Vec::new(); // (id, year, label)
        if let Some(years) = index["years"].as_object() {
            for (group_key, arr) in years {
                let Some(list) = arr.as_array() else {
                    continue;
                };
                for f in list {
                    let fid = f["id"].as_str().unwrap_or("");
                    if fid.is_empty()
                        || taken_obj.map(|o| o.contains_key(fid)).unwrap_or(false)
                    {
                        continue;
                    }
                    let year = gmat_form_year(f, group_key);
                    let label = f["label"].as_str().unwrap_or(fid).to_string();
                    forms.push((fid.to_string(), year, label));
                }
            }
        }
        if forms.is_empty() {
            return None;
        }
        forms.sort_by(|a, b| a.0.cmp(&b.0));
        let (id, year, label) = forms.into_iter().next().unwrap();
        Some(json!({ "id": id, "year": year, "label": label }))
    }

    fn gmat_build_today(&mut self, resource_dir: &str) -> Result<Value> {
        let plan = match self.get_config_optional::<Value, _>("gmatPlan") {
            Some(p) if !p.is_null() => p,
            _ => {
                return Ok(json!({
                    "has_plan": false,
                    "pacing": Value::Null,
                    "blocks": [],
                    "daily_minutes": 0,
                }))
            }
        };

        let pacing = self.gmat_pacing();
        let learned = self
            .get_config_optional::<Value, _>("gmatLearned")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let empty: Vec<Value> = Vec::new();
        let topics: Vec<Value> = plan["topics"].as_array().unwrap_or(&empty).clone();

        // due today, honoring the engine's daily limits + topic-aware order
        self.gmat_select_deck("GMAT::Quant")?;
        let queued = self.get_queued_cards(1, false)?;
        let due_total =
            queued.new_count as i64 + queued.learning_count as i64 + queued.review_count as i64;

        // which topics have an authored lesson (so "Learn"/"Repair" links resolve)
        let index = gmat_read_lessons_index(resource_dir);
        let lesson_ids: HashSet<String> = index["topics"]
            .as_array()
            .map(|arr| {
                arr.iter()
                    .filter_map(|t| t["topic_id"].as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();

        let mut blocks: Vec<Value> = Vec::new();
        const REVIEW_MIN: f64 = 1.5;
        const LESSON_MIN: f64 = 12.0;
        const PRACTICE_MIN: f64 = 2.0;
        const QUIZ_MIN: f64 = 8.0;
        const MILESTONE_MIN: f64 = 25.0;

        // DERIVED daily budget (no longer user-set): enough room for today's paced
        // lessons + the due reviews + slack. It only sizes block-filling here; the
        // RETURNED daily_minutes is the sum of the blocks actually added below.
        let reviews_est = if due_total > 0 {
            py_round(due_total as f64 * REVIEW_MIN)
        } else {
            0
        };
        let topics_per_day = py_round(pacing["topics_per_study_day"].as_f64().unwrap_or(0.0));
        let budget = 30.0_f64.max(topics_per_day as f64 * LESSON_MIN + reviews_est as f64 + 20.0);
        let mut remaining_min = budget;

        if due_total > 0 {
            let est = py_round(due_total as f64 * REVIEW_MIN);
            blocks.push(json!({
                "kind": "review",
                "title": "Spaced review",
                "detail": format!("{due_total} question(s) due today"),
                "count": due_total,
                "est_minutes": est,
            }));
            remaining_min -= est as f64;
        }

        let now_ts = TimestampMillis::now().0 / 1000;

        // repair first: relearn concept-gap topics (entries expire after 14 days)
        let repair_topics: Vec<String> = self
            .get_config_optional::<Value, _>("gmatRepairTopics")
            .filter(Value::is_object)
            .and_then(|cfg| {
                cfg.as_object().map(|o| {
                    o.iter()
                        .filter(|(t, ts)| {
                            now_ts - ts.as_i64().unwrap_or(0) < 14 * 86_400 && lesson_ids.contains(*t)
                        })
                        .map(|(t, _)| t.clone())
                        .collect()
                })
            })
            .unwrap_or_default();
        for topic in repair_topics.into_iter().take(2) {
            if remaining_min < LESSON_MIN && !blocks.is_empty() {
                break;
            }
            blocks.push(json!({
                "kind": "repair",
                "title": "Repair a concept gap",
                "detail": "you missed this on a concept - relearn, then re-apply",
                "topic": topic,
                "est_minutes": py_round(LESSON_MIN),
            }));
            remaining_min -= LESSON_MIN;
        }

        // next unlearned topics to learn today, weakest-first, paced
        let lessons_target = py_round(pacing["topics_per_study_day"].as_f64().unwrap_or(0.0)).max(1);
        let learned_obj = learned.as_object();
        let is_learned = |t: &str| learned_obj.map(|o| o.contains_key(t)).unwrap_or(false);
        let to_learn: Vec<&Value> = topics
            .iter()
            .filter(|t| {
                let tid = t["topic"].as_str().unwrap_or("");
                !is_learned(tid) && lesson_ids.contains(tid)
            })
            .collect();
        for entry in to_learn.into_iter().take(lessons_target as usize) {
            if remaining_min < LESSON_MIN && !blocks.is_empty() {
                break;
            }
            let mastery = entry["mastery"].as_f64().unwrap_or(0.5);
            blocks.push(json!({
                "kind": "learn",
                "title": "Learn a weak topic",
                "detail": format!("{} · learn it before drilling", gmat_status_str(mastery)),
                "topic": entry["topic"],
                "est_minutes": py_round(LESSON_MIN),
            }));
            remaining_min -= LESSON_MIN;
        }

        // TOPIC QUIZ (soft mastery gate): a lesson-done topic not yet mastered
        // gets a short timed quiz. One passing session needs a spaced re-quiz
        // (>= 3 days, distinct day) to reach the 2-pass gate; a recent single
        // pass waits for that spacing rather than re-quizzing today.
        let quizzes_cfg = self
            .get_config_optional::<Value, _>("gmatQuizzes")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let mut quiz_topics: Vec<(String, bool)> = Vec::new();
        for t in topics.iter() {
            let tid = t["topic"].as_str().unwrap_or("");
            if tid.is_empty() || !is_learned(tid) || !lesson_ids.contains(tid) {
                continue;
            }
            if self.gmat_topic_mastered(tid) {
                continue;
            }
            let passing: Vec<&Value> = quizzes_cfg
                .get(tid)
                .and_then(|v| v.as_array())
                .map(|arr| {
                    arr.iter()
                        .filter(|s| s["accuracy"].as_f64().unwrap_or(0.0) >= GMAT_QUIZ_PASS_ACCURACY)
                        .collect()
                })
                .unwrap_or_default();
            if passing.is_empty() {
                quiz_topics.push((tid.to_string(), false));
            } else {
                let last_pass = passing
                    .iter()
                    .map(|s| s["ts"].as_i64().unwrap_or(0))
                    .max()
                    .unwrap_or(0);
                if now_ts - last_pass >= GMAT_QUIZ_RESPACE_SECS {
                    quiz_topics.push((tid.to_string(), true));
                }
            }
        }
        for (tid, spaced) in quiz_topics.into_iter().take(2) {
            if remaining_min < QUIZ_MIN && !blocks.is_empty() {
                break;
            }
            let (title, detail) = if spaced {
                (
                    "Topic quiz (spaced)",
                    format!("confirm {} stuck - re-quiz to master", topic_leaf(&tid)),
                )
            } else {
                (
                    "Topic quiz",
                    format!("prove {} - {} questions, timed", topic_leaf(&tid), GMAT_QUIZ_N),
                )
            };
            blocks.push(json!({
                "kind": "quiz",
                "title": title,
                "detail": detail,
                "topic": tid,
                "count": GMAT_QUIZ_N,
                "est_minutes": py_round(QUIZ_MIN),
            }));
            remaining_min -= QUIZ_MIN;
        }

        // fill remaining budget with targeted practice on the weakest learned topic
        let learned_topics: Vec<&Value> = topics
            .iter()
            .filter(|t| is_learned(t["topic"].as_str().unwrap_or("")))
            .collect();
        if remaining_min >= PRACTICE_MIN && (!learned_topics.is_empty() || due_total == 0) {
            let n = ((remaining_min / PRACTICE_MIN) as i64).clamp(1, 20);
            let weak: Option<&Value> = learned_topics.first().copied().or_else(|| topics.first());
            let drill_topics: Vec<String> = self
                .get_config_optional::<Value, _>("gmatTimedDrill")
                .filter(Value::is_object)
                .and_then(|cfg| {
                    cfg.as_object().map(|o| {
                        o.iter()
                            .filter(|(_, ts)| now_ts - ts.as_i64().unwrap_or(0) < 14 * 86_400)
                            .map(|(t, _)| t.clone())
                            .collect()
                    })
                })
                .unwrap_or_default();
            let mut detail = match weak {
                Some(w) => format!("{n} extra on {}", topic_leaf(w["topic"].as_str().unwrap_or(""))),
                None => format!("{n} extra questions"),
            };
            if let Some(first_drill) = drill_topics.first() {
                detail.push_str(&format!(" · timed focus: {} (~2:08/q)", topic_leaf(first_drill)));
            }
            blocks.push(json!({
                "kind": "practice",
                "title": "Targeted practice",
                "detail": detail,
                "count": n,
                "topic": weak.map(|w| w["topic"].clone()).unwrap_or(Value::Null),
                "est_minutes": py_round(n as f64 * PRACTICE_MIN),
            }));
        }

        // ONE timed test per day, by priority: practice-test form > milestone
        // checkpoint > adaptive mock. gmatMocks now also holds milestone entries
        // (kind:"milestone"), so the practice-test/adaptive-mock cadence reads
        // only NON-milestone entries to stay exactly as before, while the
        // milestone has its own weekly cadence and an "already tested today"
        // guard keeps it to one timed test a day.
        let mocks = self
            .get_config_optional::<Vec<Value>, _>("gmatMocks")
            .unwrap_or_default();
        let last_mock_ts = mocks
            .iter()
            .filter(|m| m.get("kind").and_then(|k| k.as_str()) != Some("milestone"))
            .last()
            .and_then(|m| m.get("ts"))
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        let last_milestone_ts = mocks
            .iter()
            .filter(|m| m.get("kind").and_then(|k| k.as_str()) == Some("milestone"))
            .last()
            .and_then(|m| m.get("ts"))
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        let cutoff = self
            .timing_today()
            .map(|t| t.next_day_at.0)
            .unwrap_or(now_ts);
        let today_start_ts = cutoff - 86_400;
        let taken_timed_today = mocks
            .iter()
            .any(|m| m.get("ts").and_then(|v| v.as_i64()).unwrap_or(0) >= today_start_ts);

        let days_to_exam = pacing["days_to_exam"].as_i64();
        let topics_learned = pacing["topics_learned"].as_i64().unwrap_or(0);
        let topics_total = pacing["topics_total"].as_i64().unwrap_or(0);
        let lesson_done_count = learned_topics.len() as i64;
        let learning_ok = pacing["status"].as_str() == Some("learning_complete")
            || (topics_total > 0
                && topics_learned as f64 / topics_total as f64 >= GMAT_TEST_MIN_LEARNED_FRAC);
        let near_exam = days_to_exam
            .map(|d| d <= GMAT_TEST_EXAM_WINDOW_DAYS)
            .unwrap_or(false);

        let mut timed_block: Option<Value> = None;
        // 1) practice-test form (unchanged cadence, near the exam)
        if let Some(dte) = days_to_exam {
            if let Some(form) = self.gmat_next_untaken_test(resource_dir) {
                let cadence_days = if dte <= 14 {
                    4
                } else if dte <= 21 {
                    7
                } else {
                    10
                };
                if (now_ts - last_mock_ts) > cadence_days * 86_400 && near_exam && learning_ok {
                    let label = form["label"].as_str().unwrap_or("").to_string();
                    timed_block = Some(json!({
                        "kind": "mock",
                        "title": "Practice test",
                        "detail": format!("{label} - 21 questions, timed"),
                        "form_id": form["id"],
                        "label": label,
                        "est_minutes": 45,
                    }));
                }
            }
        }

        // 2) milestone checkpoint: roughly weekly once several topics are learned
        if timed_block.is_none()
            && lesson_done_count >= GMAT_MILESTONE_MIN_TOPICS
            && (now_ts - last_milestone_ts) > 7 * 86_400
        {
            timed_block = Some(json!({
                "kind": "milestone",
                "title": "Milestone test",
                "detail": format!(
                    "{GMAT_MILESTONE_N} questions, mixed across learned topics · timed"
                ),
                "count": GMAT_MILESTONE_N,
                "est_minutes": py_round(MILESTONE_MIN),
            }));
        }

        // 3) adaptive mock section (existing fallback)
        if timed_block.is_none() {
            let mock_due = (pacing["status"].as_str() == Some("learning_complete")
                || (days_to_exam.map(|d| d <= 21).unwrap_or(false) && learning_ok))
                && (now_ts - last_mock_ts) > 7 * 86_400;
            if mock_due {
                timed_block = Some(json!({
                    "kind": "mock",
                    "title": "Timed mock section",
                    "detail": "21 questions · 45:00 · exam conditions, no feedback until the end",
                    "count": 21,
                    "est_minutes": 45,
                }));
            }
        }

        if let Some(block) = timed_block {
            if !taken_timed_today {
                blocks.push(block);
            }
        }

        let total_est: i64 = blocks
            .iter()
            .map(|b| b["est_minutes"].as_i64().unwrap_or(0))
            .sum();
        Ok(json!({
            "has_plan": true,
            "pacing": pacing,
            "blocks": blocks,
            "daily_minutes": total_est,
        }))
    }

    /// A tentative day-by-day study calendar from today through the exam
    /// (mirrors `_gmat_build_calendar`). Everything is DERIVED from the current
    /// plan/mastery/learned/quiz state, so each fetch recalibrates; it parallels
    /// `gmat_pacing` + `gmat_build_today` (same 10-day hard boundary, late_start,
    /// weakest-first topics, per-item minute costs). `{ "days": [] }` without a
    /// plan/exam date so the UI can show an empty state.
    fn gmat_build_calendar(&self) -> Value {
        // per-item minute costs mirror the Today builder
        const LESSON_MIN: f64 = 12.0;
        const QUIZ_MIN: f64 = 8.0;
        const MILESTONE_MIN: f64 = 25.0;
        const PRACTICE_MIN: f64 = 2.0;
        const PRACTICE_TEST_MIN: f64 = 45.0;
        const CAL_DRILL_N: i64 = 8;
        const CAL_TEST_CADENCE: i64 = 4;
        const CAL_MAX_DAYS: i64 = 370;

        let now_ts = TimestampMillis::now().0 / 1000;
        let empty = json!({
            "exam_date": "",
            "days_to_exam": Value::Null,
            "generated_ts": now_ts,
            "study_days": 0,
            "lessons_finish_date": Value::Null,
            "days": [],
        });
        let plan = match self.get_config_optional::<Value, _>("gmatPlan") {
            Some(p) if p.is_object() => p,
            _ => return empty,
        };
        let profile = self
            .get_config_optional::<Value, _>("gmatProfile")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let exam_date = profile["exam_date"].as_str().unwrap_or("").to_string();
        if exam_date.is_empty() {
            return empty;
        }
        let Ok(exam) = NaiveDate::parse_from_str(&exam_date, "%Y-%m-%d") else {
            return empty;
        };
        let today = Local::now().date_naive();
        let days_to_exam = (exam - today).num_days();
        if days_to_exam < 0 {
            let mut out = empty.clone();
            out["exam_date"] = json!(exam_date);
            out["days_to_exam"] = json!(days_to_exam);
            return out;
        }

        let pacing = self.gmat_pacing();
        // match `_gmat_pacing`'s days_per_week (0 -> 5), then clamp to [1,7] so the
        // study-day pattern is meaningful for the calendar's rolling-week rule
        let days_per_week = {
            let d = plan
                .get("days_per_week")
                .and_then(|v| v.as_i64())
                .or_else(|| profile.get("days_per_week").and_then(|v| v.as_i64()))
                .unwrap_or(5);
            (if d == 0 { 5 } else { d }).clamp(1, 7)
        };
        let late_start = pacing["late_start"].as_bool().unwrap_or(false);

        // DERIVED from current mastery + learned state (so each fetch
        // recalibrates): remaining = UN-MASTERED topics weakest-first. A topic
        // already lesson-done ("learned") but not mastered projects its mastery
        // quizzes only - no fresh lesson - like the Today builder, so pulling a
        // lesson forward (jump-ahead) turns its future slot from lesson -> quiz.
        let learned = self
            .get_config_optional::<Value, _>("gmatLearned")
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        let learned_ids: HashSet<String> = learned
            .as_object()
            .map(|o| o.keys().cloned().collect())
            .unwrap_or_default();
        let empty_vec: Vec<Value> = Vec::new();
        let topics = plan["topics"].as_array().unwrap_or(&empty_vec);
        let remaining: Vec<String> = topics
            .iter()
            .filter_map(|t| t["topic"].as_str().map(String::from))
            .filter(|t| !t.is_empty() && !self.gmat_topic_mastered(t))
            .collect();
        // lesson-done topics count toward "learned" for review scaling + the
        // milestone gate (mirrors the Today builder's lesson_done_count)
        let lesson_done_start = topics
            .iter()
            .filter(|t| {
                t["topic"]
                    .as_str()
                    .map(|s| learned_ids.contains(s))
                    .unwrap_or(false)
            })
            .count() as i64;

        const WEEKDAYS: [&str; 7] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        // HARD boundary: lessons finish by exam-10; last 10 days are tests-only
        let final_start = days_to_exam - 10;
        let is_study = |off: i64| -> bool { off.rem_euclid(7) < days_per_week };
        let next_study = |off: i64| -> Option<i64> {
            let mut o = off + 1;
            while o < days_to_exam {
                if is_study(o) {
                    return Some(o);
                }
                o += 1;
            }
            None
        };
        let study_at_least = |off: i64| -> Option<i64> {
            let mut o = off.max(0);
            while o < days_to_exam {
                if is_study(o) {
                    return Some(o);
                }
                o += 1;
            }
            None
        };

        // eligible study days for lessons: the learn window, unless a late start
        // pushes lessons across ALL remaining study days (mirrors pacing)
        let eligible: Vec<i64> = (0..days_to_exam)
            .filter(|&o| is_study(o) && (late_start || o < final_start))
            .collect();

        let mut lessons_by: HashMap<i64, Vec<String>> = HashMap::new();
        let mut quizzes_by: HashMap<i64, Vec<String>> = HashMap::new();
        let mut requizzes_by: HashMap<i64, Vec<String>> = HashMap::new();

        // spread the remaining topics EVENLY across the eligible study days
        // (spacing ~= eligible/remaining, i.e. ~topics_per_study_day/day). A
        // not-yet-taught topic gets a lesson, a quiz the next study day, and a
        // spaced re-quiz ~3 days on; an already-taught (learned) topic skips the
        // lesson and just gets its quiz + spaced re-quiz.
        let respace_days = GMAT_QUIZ_RESPACE_SECS / 86_400;
        let r = remaining.len();
        let e = eligible.len();
        if r > 0 && e > 0 {
            for k in 0..r {
                let di = ((k * e) / r).min(e - 1);
                let o = eligible[di];
                let topic = remaining[k].clone();
                if learned_ids.contains(&topic) {
                    quizzes_by.entry(o).or_default().push(topic.clone());
                    if let Some(rq_off) = study_at_least(o + respace_days) {
                        requizzes_by.entry(rq_off).or_default().push(topic);
                    }
                } else {
                    lessons_by.entry(o).or_default().push(topic.clone());
                    if let Some(q_off) = next_study(o) {
                        quizzes_by.entry(q_off).or_default().push(topic.clone());
                        if let Some(rq_off) = study_at_least(q_off + respace_days) {
                            requizzes_by.entry(rq_off).or_default().push(topic);
                        }
                    }
                }
            }
        }

        let last_lesson_off = lessons_by.keys().copied().max().unwrap_or(-1);

        // cumulative topics learned by each offset (already lesson-done + lessons
        // placed up to and including that day) -> review scaling + milestone gate
        let mut prefix = vec![0i64; (days_to_exam + 1) as usize];
        for (o2, tps) in &lessons_by {
            if *o2 >= 0 && *o2 <= days_to_exam {
                prefix[*o2 as usize] += tps.len() as i64;
            }
        }
        let mut run = 0i64;
        for slot in prefix.iter_mut() {
            run += *slot;
            *slot = run;
        }
        let learned_upto =
            |off: i64| -> i64 { lesson_done_start + prefix[off.clamp(0, days_to_exam) as usize] };

        // milestone ~ every 7th study day (learn/review window) once >= 3 learned
        let mut milestones: HashSet<i64> = HashSet::new();
        let mut s = 0i64;
        for o in 0..days_to_exam {
            if !is_study(o) {
                continue;
            }
            s += 1;
            if s % 7 == 0 && o < final_start && learned_upto(o) >= GMAT_MILESTONE_MIN_TOPICS {
                milestones.insert(o);
            }
        }

        // practice tests spaced through the final stretch at the near-exam cadence
        let mut practice_tests: HashSet<i64> = HashSet::new();
        let mut last_test = -CAL_TEST_CADENCE - 1;
        for o in final_start.max(0)..days_to_exam {
            if is_study(o) && o - last_test >= CAL_TEST_CADENCE {
                practice_tests.insert(o);
                last_test = o;
            }
        }

        let mut days_out: Vec<Value> = Vec::new();
        let end = days_to_exam.min(CAL_MAX_DAYS);
        for off in 0..=end {
            let d = today + Duration::days(off);
            let is_exam = off == days_to_exam;
            let study = is_study(off) && !is_exam;
            let has_lesson = lessons_by.contains_key(&off);
            let has_test = practice_tests.contains(&off);
            let has_ms = milestones.contains(&off);
            let mut items: Vec<Value> = Vec::new();
            let phase: &str;
            if is_exam {
                phase = "final";
            } else {
                if study {
                    items.push(json!({
                        "kind": "review",
                        "topic": Value::Null,
                        "title": "Spaced review",
                        "est_minutes": gmat_cal_review_min(learned_upto(off)),
                    }));
                    if let Some(tps) = lessons_by.get(&off) {
                        for tp in tps {
                            items.push(json!({
                                "kind": "lesson",
                                "topic": tp,
                                "title": format!("Learn {}", topic_leaf(tp)),
                                "est_minutes": py_round(LESSON_MIN),
                            }));
                        }
                    }
                    if let Some(tps) = quizzes_by.get(&off) {
                        for tp in tps {
                            items.push(json!({
                                "kind": "quiz",
                                "topic": tp,
                                "title": format!("Quiz: {}", topic_leaf(tp)),
                                "est_minutes": py_round(QUIZ_MIN),
                            }));
                        }
                    }
                    if let Some(tps) = requizzes_by.get(&off) {
                        for tp in tps {
                            items.push(json!({
                                "kind": "requiz",
                                "topic": tp,
                                "title": format!("Re-quiz: {}", topic_leaf(tp)),
                                "est_minutes": py_round(QUIZ_MIN),
                            }));
                        }
                    }
                    if has_ms {
                        items.push(json!({
                            "kind": "milestone",
                            "topic": Value::Null,
                            "title": "Milestone checkpoint",
                            "est_minutes": py_round(MILESTONE_MIN),
                        }));
                    }
                    if has_test {
                        items.push(json!({
                            "kind": "practice_test",
                            "topic": Value::Null,
                            "title": "Practice test",
                            "est_minutes": py_round(PRACTICE_TEST_MIN),
                        }));
                    }
                    // a non-lesson study day (no lesson/test/milestone) gets a drill fill
                    if !has_lesson && !has_test && !has_ms {
                        items.push(json!({
                            "kind": "drill",
                            "topic": Value::Null,
                            "title": "Targeted drill",
                            "est_minutes": py_round(CAL_DRILL_N as f64 * PRACTICE_MIN),
                        }));
                    }
                } else {
                    items.push(json!({
                        "kind": "rest",
                        "topic": Value::Null,
                        "title": "Rest day",
                        "est_minutes": 0,
                    }));
                }
                // phase: content-first (a lesson day is "learn"), else by window
                phase = if has_lesson {
                    "learn"
                } else if off >= final_start {
                    "final"
                } else if off > last_lesson_off {
                    "review"
                } else {
                    "learn"
                };
            }
            let est: i64 = items
                .iter()
                .map(|it| it["est_minutes"].as_i64().unwrap_or(0))
                .sum();
            days_out.push(json!({
                "date": d.format("%Y-%m-%d").to_string(),
                "day_offset": off,
                "weekday": WEEKDAYS[d.weekday().num_days_from_monday() as usize],
                "is_today": off == 0,
                "is_exam": is_exam,
                "is_study_day": study,
                "phase": phase,
                "est_minutes": est,
                "items": items,
            }));
        }

        let lessons_finish_date = if last_lesson_off >= 0 {
            json!((today + Duration::days(last_lesson_off))
                .format("%Y-%m-%d")
                .to_string())
        } else {
            Value::Null
        };
        let study_days = (0..days_to_exam).filter(|&o| is_study(o)).count() as i64;
        json!({
            "exam_date": exam_date,
            "days_to_exam": days_to_exam,
            "generated_ts": now_ts,
            "study_days": study_days,
            "lessons_finish_date": lessons_finish_date,
            "days": days_out,
        })
    }

    /// Store a finished mock, update the living plan, and return the report
    /// (mirrors `gmat_submit_mock`). Mock answers do NOT go through the scheduler.
    fn gmat_submit_mock(&mut self, body: &Value, now: i64) -> Result<String> {
        const TARGET_MS: i64 = 128_000;
        let results = body["results"].as_array().cloned().unwrap_or_default();
        let n = results.len();
        if n == 0 {
            return Ok(json!({ "ok": false }).to_string());
        }
        // optional: which practice-test form produced these answers (year is
        // accepted for client symmetry but resolved from the index, so unused).
        let form_id = body["form_id"].as_str().unwrap_or("").to_string();
        let correct_count = results
            .iter()
            .filter(|r| r["correct"].as_bool().unwrap_or(false))
            .count();
        let accuracy = correct_count as f64 / n as f64;
        let acc_round = (accuracy * 10_000.0).round() / 10_000.0;

        let timed: Vec<(bool, i64)> = results
            .iter()
            .filter_map(|r| {
                let ms = json_i64(&r["ms"], 0);
                if ms > 0 {
                    Some((r["correct"].as_bool().unwrap_or(false), ms))
                } else {
                    None
                }
            })
            .collect();
        let rushed_wrong = timed.iter().filter(|(c, ms)| !c && *ms < TARGET_MS / 2).count();
        let slow_correct = timed
            .iter()
            .filter(|(c, ms)| *c && *ms > TARGET_MS * 3 / 2)
            .count();
        let avg_ms = if timed.is_empty() {
            0
        } else {
            timed.iter().map(|(_, ms)| ms).sum::<i64>() / timed.len() as i64
        };

        let mut per_topic: HashMap<String, (i64, i64)> = HashMap::new();
        let mut order: Vec<String> = Vec::new();
        for r in &results {
            let topic = r["topic"].as_str().unwrap_or("").to_string();
            let is_c = r["correct"].as_bool().unwrap_or(false);
            if topic.is_empty() {
                continue;
            }
            if !per_topic.contains_key(&topic) {
                order.push(topic.clone());
            }
            {
                let e = per_topic.entry(topic.clone()).or_insert((0, 0));
                e.1 += 1;
                if is_c {
                    e.0 += 1;
                }
            }
            // every mock answer updates the living plan, like practice answers do
            self.gmat_update_mastery(&topic, is_c, GMAT_MASTERY_ALPHA)?;
        }

        let mut mocks = self
            .get_config_optional::<Vec<Value>, _>("gmatMocks")
            .unwrap_or_default();
        let mut mock_entry = json!({
            "ts": now,
            "accuracy": acc_round,
            "n": n,
            "timing": {
                "avg_ms": avg_ms,
                "rushed_wrong": rushed_wrong,
                "slow_correct": slow_correct,
            },
        });
        if !form_id.is_empty() {
            mock_entry["form_id"] = json!(form_id);
        }
        mocks.push(mock_entry);
        let start = mocks.len().saturating_sub(20);
        let trimmed = mocks[start..].to_vec();
        self.gmat_put_config("gmatMocks", &Value::Array(trimmed))?;

        // score the mock in the shared engine (single accuracy->Q implementation)
        let q = match self.gmat_scores_json() {
            Ok(s) => serde_json::from_str::<Value>(&s)
                .ok()
                .and_then(|scores| {
                    scores["readiness"]["mocks"]
                        .as_array()
                        .and_then(|m| m.last())
                        .and_then(|last| last.get("q").cloned())
                })
                .unwrap_or(Value::Null),
            Err(_) => Value::Null,
        };

        // a practice-test form additionally records itself as taken (id -> score)
        if !form_id.is_empty() {
            let mut taken = self
                .get_config_optional::<Value, _>("gmatTestsTaken")
                .filter(Value::is_object)
                .unwrap_or_else(|| json!({}));
            taken.as_object_mut().unwrap().insert(
                form_id.clone(),
                json!({ "ts": now, "accuracy": acc_round, "q": q }),
            );
            self.gmat_put_config("gmatTestsTaken", &taken)?;
        }

        let mut pt: Vec<(String, (i64, i64))> =
            order.iter().map(|t| (t.clone(), per_topic[t])).collect();
        pt.sort_by(|a, b| {
            let (ca, ta) = a.1;
            let (cb, tb) = b.1;
            (ca as f64 / ta as f64)
                .partial_cmp(&(cb as f64 / tb as f64))
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        let per_topic_json: Vec<Value> = pt
            .iter()
            .map(|(t, ct)| json!({ "topic": t, "correct": ct.0, "n": ct.1 }))
            .collect();

        Ok(json!({
            "ok": true,
            "accuracy": acc_round,
            "n": n,
            "q": q,
            "per_topic": per_topic_json,
            "timing": {
                "avg_ms": avg_ms,
                "rushed_wrong": rushed_wrong,
                "slow_correct": slow_correct,
                "target_ms": TARGET_MS,
            },
        })
        .to_string())
    }

    /// Store a finished assessment session (topic quiz / milestone test) and
    /// return its report (mirrors `gmat_submit_quiz`). Feeds all three scores:
    /// topic quiz appends to gmatQuizzes (the mastery gate) and re-enters repair
    /// on failure; milestone appends to gmatMocks with kind:"milestone" so
    /// Readiness folds it in. Both move mastery harder (0.5) and log every answer
    /// as an application attempt (gmatApplication) for Performance. Assessment
    /// answers do NOT go through the scheduler.
    fn gmat_submit_quiz(&mut self, body: &Value, now: i64) -> Result<String> {
        const TARGET_MS: i64 = 128_000;
        let kind = body["kind"].as_str().unwrap_or("topic").to_string();
        let results = body["results"].as_array().cloned().unwrap_or_default();
        let n = results.len();
        if n == 0 {
            return Ok(json!({ "ok": false }).to_string());
        }
        let correct_count = results
            .iter()
            .filter(|r| r["correct"].as_bool().unwrap_or(false))
            .count();
        let accuracy = correct_count as f64 / n as f64;
        let acc_round = (accuracy * 10_000.0).round() / 10_000.0;

        let timed: Vec<(bool, i64)> = results
            .iter()
            .filter_map(|r| {
                let ms = json_i64(&r["ms"], 0);
                if ms > 0 {
                    Some((r["correct"].as_bool().unwrap_or(false), ms))
                } else {
                    None
                }
            })
            .collect();
        let rushed_wrong = timed.iter().filter(|(c, ms)| !c && *ms < TARGET_MS / 2).count();
        let slow_correct = timed
            .iter()
            .filter(|(c, ms)| *c && *ms > TARGET_MS * 3 / 2)
            .count();
        let avg_ms = if timed.is_empty() {
            0
        } else {
            timed.iter().map(|(_, ms)| ms).sum::<i64>() / timed.len() as i64
        };

        let mut per_topic: HashMap<String, (i64, i64)> = HashMap::new();
        let mut order: Vec<String> = Vec::new();
        for r in &results {
            let topic = r["topic"].as_str().unwrap_or("").to_string();
            let is_c = r["correct"].as_bool().unwrap_or(false);
            if topic.is_empty() {
                continue;
            }
            if !per_topic.contains_key(&topic) {
                order.push(topic.clone());
            }
            {
                let e = per_topic.entry(topic.clone()).or_insert((0, 0));
                e.1 += 1;
                if is_c {
                    e.0 += 1;
                }
            }
            // assessment answers move mastery harder (0.5) + are application evidence
            self.gmat_update_mastery(&topic, is_c, GMAT_QUIZ_MASTERY_ALPHA)?;
            self.gmat_record_application(&topic, is_c, json_i64(&r["ms"], 0), now)?;
        }

        let mut mastered: Option<bool> = None;
        if kind == "milestone" {
            let mut mocks = self
                .get_config_optional::<Vec<Value>, _>("gmatMocks")
                .unwrap_or_default();
            mocks.push(json!({
                "ts": now,
                "kind": "milestone",
                "accuracy": acc_round,
                "n": n,
                "timing": {
                    "avg_ms": avg_ms,
                    "rushed_wrong": rushed_wrong,
                    "slow_correct": slow_correct,
                },
            }));
            let start = mocks.len().saturating_sub(20);
            let trimmed = mocks[start..].to_vec();
            self.gmat_put_config("gmatMocks", &Value::Array(trimmed))?;
        } else {
            let mut topic = body["topic"].as_str().unwrap_or("").to_string();
            if topic.is_empty() {
                // infer the dominant topic if the client omitted it
                topic = order
                    .iter()
                    .max_by_key(|t| per_topic.get(*t).map(|c| c.1).unwrap_or(0))
                    .cloned()
                    .unwrap_or_default();
            }
            if !topic.is_empty() {
                let day = self.gmat_day_bucket();
                let mut quizzes = self
                    .get_config_optional::<Value, _>("gmatQuizzes")
                    .filter(Value::is_object)
                    .unwrap_or_else(|| json!({}));
                let mut sessions = quizzes
                    .get(&topic)
                    .and_then(|v| v.as_array())
                    .cloned()
                    .unwrap_or_default();
                sessions.push(json!({ "ts": now, "day": day, "accuracy": acc_round, "n": n }));
                let start = sessions.len().saturating_sub(50);
                let trimmed = sessions[start..].to_vec();
                quizzes
                    .as_object_mut()
                    .unwrap()
                    .insert(topic.clone(), Value::Array(trimmed));
                self.gmat_put_config("gmatQuizzes", &quizzes)?;
                let is_mastered = self.gmat_topic_mastered(&topic);
                mastered = Some(is_mastered);
                if accuracy < GMAT_QUIZ_PASS_ACCURACY {
                    self.gmat_apply_repair(&topic, "concept_gap")?;
                } else if is_mastered {
                    let mut repairs = self
                        .get_config_optional::<Value, _>("gmatRepairTopics")
                        .filter(Value::is_object)
                        .unwrap_or_else(|| json!({}));
                    let had = repairs
                        .as_object()
                        .map(|o| o.contains_key(&topic))
                        .unwrap_or(false);
                    if had {
                        repairs.as_object_mut().unwrap().remove(&topic);
                        self.gmat_put_config("gmatRepairTopics", &repairs)?;
                    }
                }
            }
        }

        // score in the shared engine (single accuracy->Q map); a milestone shows
        // a Q like a mock, a topic quiz reports accuracy without a section score
        let q = if kind == "milestone" {
            match self.gmat_scores_json() {
                Ok(s) => serde_json::from_str::<Value>(&s)
                    .ok()
                    .and_then(|scores| {
                        scores["readiness"]["mocks"]
                            .as_array()
                            .and_then(|m| m.last())
                            .and_then(|last| last.get("q").cloned())
                    })
                    .unwrap_or(Value::Null),
                Err(_) => Value::Null,
            }
        } else {
            Value::Null
        };

        let mut pt: Vec<(String, (i64, i64))> =
            order.iter().map(|t| (t.clone(), per_topic[t])).collect();
        pt.sort_by(|a, b| {
            let (ca, ta) = a.1;
            let (cb, tb) = b.1;
            (ca as f64 / ta as f64)
                .partial_cmp(&(cb as f64 / tb as f64))
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        let per_topic_json: Vec<Value> = pt
            .iter()
            .map(|(t, ct)| json!({ "topic": t, "correct": ct.0, "n": ct.1 }))
            .collect();

        let mut report = json!({
            "ok": true,
            "kind": kind,
            "accuracy": acc_round,
            "n": n,
            "q": q,
            "per_topic": per_topic_json,
            "timing": {
                "avg_ms": avg_ms,
                "rushed_wrong": rushed_wrong,
                "slow_correct": slow_correct,
                "target_ms": TARGET_MS,
            },
        });
        if let Some(m) = mastered {
            report["mastered"] = json!(m);
        }
        Ok(report.to_string())
    }

    /// Dispatch a GMATWiz web endpoint (the iOS equivalent of the desktop's
    /// `qt/aqt/mediasrv.py` `gmat_*` POST handlers). `name` is the camelCase
    /// method, `body` the POST JSON (possibly empty), `resource_dir` the bundled
    /// `gmatwiz/` folder (lessons/ + content/). Returns the same JSON the Python
    /// handler returns (or an empty string where the handler returns `b""`).
    pub fn gmat_endpoint(&mut self, name: &str, body: &str, resource_dir: &str) -> Result<String> {
        let now = TimestampMillis::now().0 / 1000;
        let out = match name {
            "gmatOverview" => {
                // NOTE: the desktop `_ensure_gmat_time_cap` (raising the deck's
                // maxTaken) is intentionally not ported here - the mobile answer
                // path already caps ms - so overview stays a pure read.
                let total = self.gmat_count("note:\"GMAT PS\"");
                let new = self.gmat_count("note:\"GMAT PS\" is:new");
                let due = self.gmat_count("note:\"GMAT PS\" (is:due OR is:learn)");
                let reviews: i64 = self
                    .storage
                    .db
                    .query_row("select count() from revlog", [], |r| r.get(0))
                    .unwrap_or(0);
                let scores = match self.gmat_scores_json() {
                    Ok(s) => {
                        serde_json::from_str::<Value>(&s).unwrap_or_else(|_| gmat_scores_fallback(now))
                    }
                    Err(_) => gmat_scores_fallback(now),
                };
                let profile = self
                    .get_config_optional::<Value, _>("gmatProfile")
                    .unwrap_or(Value::Null);
                let plan = self
                    .get_config_optional::<Value, _>("gmatPlan")
                    .unwrap_or(Value::Null);
                // null when unset (so the app can prefer synced over local); a
                // real bool once the user has toggled AI on any device.
                let ai_enabled = match self.get_config_optional::<bool, _>("gmatAiEnabled") {
                    Some(b) => json!(b),
                    None => Value::Null,
                };
                json!({
                    "deck": "GMAT::Quant",
                    "total": total,
                    "new": new,
                    "due": due,
                    "reviews": reviews,
                    "topics_covered": scores["topics_covered"],
                    "topics_total": scores["topics_total"],
                    "memory": scores["memory"],
                    "performance": scores["performance"],
                    "readiness": scores["readiness"],
                    "profile": profile,
                    "plan": plan,
                    "gmatAiEnabled": ai_enabled,
                })
                .to_string()
            }
            "gmatQuestions" => {
                let questions: Vec<Value> = self
                    .gmat_question_pool(resource_dir)?
                    .iter()
                    .map(GmatNoteFields::question_json)
                    .collect();
                json!({ "questions": questions }).to_string()
            }
            "gmatNextCard" => {
                self.gmat_select_deck("GMAT::Quant")?;
                let queued = self.get_queued_cards(1, false)?;
                let counts = json!({
                    "new": queued.new_count,
                    "learning": queued.learning_count,
                    "review": queued.review_count,
                });
                let card = if let Some(qc) = queued.cards.first() {
                    let note = self
                        .storage
                        .get_note(qc.card.note_id())?
                        .or_not_found(qc.card.note_id())?;
                    let names = self.storage.get_field_names(note.notetype_id)?;
                    let vals = note.fields();
                    json!({
                        "card_id": qc.card.id().0,
                        "stem": field_value(&names, vals, "Stem"),
                        "options": {
                            "A": field_value(&names, vals, "OptionA"),
                            "B": field_value(&names, vals, "OptionB"),
                            "C": field_value(&names, vals, "OptionC"),
                            "D": field_value(&names, vals, "OptionD"),
                            "E": field_value(&names, vals, "OptionE"),
                        },
                        "correct": field_value(&names, vals, "Correct"),
                        "explanation": field_value(&names, vals, "Explanation"),
                        "topic": field_value(&names, vals, "Topic"),
                        "difficulty": field_value(&names, vals, "Difficulty"),
                    })
                } else {
                    Value::Null
                };
                json!({ "card": card, "counts": counts }).to_string()
            }
            "gmatAnswerCard" => {
                let body = parse_body(body);
                let card_id = json_i64(&body["card_id"], 0);
                let correct = body["correct"].as_bool().unwrap_or(false);
                let ms = json_i64(&body["ms"], 0).clamp(0, u32::MAX as i64) as u32;
                self.gmat_select_deck("GMAT::Quant")?;
                // answer through the real scheduler; if the queue moved on, the
                // helper errors and we skip silently (matches Python's b"" path),
                // updating mastery only when a real answer landed.
                if self.gmat_mobile_answer(card_id, correct, ms).is_ok() {
                    let topic = self.gmat_topic_of_card(card_id)?;
                    self.gmat_update_mastery(&topic, correct, GMAT_MASTERY_ALPHA)?;
                }
                String::new()
            }
            "gmatSaveProfile" => {
                let body = parse_body(body);
                let days = {
                    let d = json_i64(&body["days_per_week"], 5);
                    if d == 0 {
                        5
                    } else {
                        d
                    }
                };
                let target = {
                    let t = json_i64(&body["target_score"], 645);
                    let t = if t == 0 { 645 } else { t };
                    t.clamp(205, 805)
                };
                let profile = json!({
                    "exam_date": body["exam_date"].as_str().unwrap_or(""),
                    "days_per_week": days,
                    "target_score": target,
                });
                self.gmat_put_config("gmatProfile", &profile)?;
                String::new()
            }
            "gmatSetAiEnabled" => {
                // Mirror the AI on/off choice to synced config (parity with the
                // desktop mediasrv handler) so it follows the account.
                let body = parse_body(body);
                let enabled = body["enabled"].as_bool().unwrap_or(false);
                self.gmat_put_config("gmatAiEnabled", &json!(enabled))?;
                json!({ "ok": true }).to_string()
            }
            "gmatAddQuestions" => {
                // No-op on mobile: rslib has no notetype importer, so generated
                // items can't become real FSRS notes here. The client detects the
                // {added:0} response and practices the batch EPHEMERALLY instead
                // (still logging wrong answers to the error log). TODO: port
                // anki.gmatwiz.build_add_requests to rslib to persist on mobile.
                json!({ "added": 0 }).to_string()
            }
            "gmatToday" => match self.gmat_build_today(resource_dir) {
                Ok(v) => v.to_string(),
                Err(_) => json!({
                    "has_plan": false,
                    "pacing": Value::Null,
                    "blocks": [],
                    "daily_minutes": 0,
                })
                .to_string(),
            },
            "gmatCalendar" => self.gmat_build_calendar().to_string(),
            "gmatStats" => self.gmat_stats_json()?,
            "gmatOfficialScores" => {
                let scores = self
                    .get_config_optional::<Vec<Value>, _>("gmatOfficialScores")
                    .unwrap_or_default();
                let reversed: Vec<Value> = scores.into_iter().rev().collect();
                json!({ "scores": reversed }).to_string()
            }
            "gmatSaveOfficialScore" => {
                let body = parse_body(body);
                let quant = json_i64(&body["quant"], 0);
                if !(60..=90).contains(&quant) {
                    return Ok(json!({ "ok": false, "error": "Quant must be 60-90." }).to_string());
                }
                let projection = self.gmat_current_projection();
                let entry = json!({
                    "ts": now,
                    "date": body["date"].as_str().unwrap_or(""),
                    "quant": quant,
                    "total": json_opt_i64(&body["total"]),
                    "verbal": json_opt_i64(&body["verbal"]),
                    "di": json_opt_i64(&body["di"]),
                    "projected_at_entry": projection,
                });
                let mut scores = self
                    .get_config_optional::<Vec<Value>, _>("gmatOfficialScores")
                    .unwrap_or_default();
                scores.push(entry.clone());
                let start = scores.len().saturating_sub(50);
                let trimmed = scores[start..].to_vec();
                self.gmat_put_config("gmatOfficialScores", &Value::Array(trimmed))?;
                json!({ "ok": true, "entry": entry }).to_string()
            }
            "gmatPretestQuestions" => {
                let pool = self.gmat_question_pool(resource_dir)?;
                let mut by_topic: HashMap<String, Vec<usize>> = HashMap::new();
                for (i, q) in pool.iter().enumerate() {
                    if !q.topic.is_empty() {
                        by_topic.entry(q.topic.clone()).or_default().push(i);
                    }
                }
                let mut rng = rand::rng();
                let mut picked: Vec<usize> = Vec::new();
                let mut seen: HashSet<usize> = HashSet::new();
                for idxs in by_topic.values() {
                    if let Some(&choice) = idxs.choose(&mut rng) {
                        picked.push(choice);
                        seen.insert(choice);
                    }
                }
                let mut all: Vec<usize> = by_topic.values().flatten().copied().collect();
                all.shuffle(&mut rng);
                for idx in all {
                    if picked.len() >= 21 {
                        break;
                    }
                    if seen.insert(idx) {
                        picked.push(idx);
                    }
                }
                picked.truncate(21);
                picked.shuffle(&mut rng);
                let questions: Vec<Value> = picked.iter().map(|&i| pool[i].pretest_json()).collect();
                json!({ "questions": questions, "seconds": 45 * 60 }).to_string()
            }
            "gmatSubmitPretest" => self.gmat_submit_pretest(&parse_body(body), resource_dir, now)?,
            "gmatLessonsIndex" => self.gmat_lessons_index_json(resource_dir),
            "gmatLesson" => {
                let body = parse_body(body);
                let topic_id = body["topic_id"].as_str().unwrap_or("");
                let lesson = gmat_read_lesson_by_topic(resource_dir, topic_id).unwrap_or(Value::Null);
                json!({ "lesson": lesson }).to_string()
            }
            "gmatMarkLearned" => {
                let body = parse_body(body);
                let topic_id = body["topic_id"].as_str().unwrap_or("").to_string();
                if !topic_id.is_empty() {
                    let mut learned = self
                        .get_config_optional::<Value, _>("gmatLearned")
                        .filter(Value::is_object)
                        .unwrap_or_else(|| json!({}));
                    learned
                        .as_object_mut()
                        .unwrap()
                        .insert(topic_id.clone(), json!(now));
                    self.gmat_put_config("gmatLearned", &learned)?;
                    // TODO(mobile): the desktop `_schedule_lesson_items` imports
                    // the lesson's you-do items as GMAT PS cards; rslib has no
                    // notetype importer yet, so completion is recorded and we
                    // report scheduled:0 rather than risk breaking the deck.
                    let mut repairs = self
                        .get_config_optional::<Value, _>("gmatRepairTopics")
                        .filter(Value::is_object)
                        .unwrap_or_else(|| json!({}));
                    let had_repair = repairs
                        .as_object()
                        .map(|o| o.contains_key(&topic_id))
                        .unwrap_or(false);
                    if had_repair {
                        repairs.as_object_mut().unwrap().remove(&topic_id);
                        self.gmat_put_config("gmatRepairTopics", &repairs)?;
                    }
                }
                json!({ "scheduled": 0 }).to_string()
            }
            "gmatLogError" => {
                let entry = parse_body(body);
                let topic = entry["topic"].as_str().unwrap_or("").to_string();
                let why = entry["why"].as_str().unwrap_or("").to_string();
                let stem: String = entry["stem"].as_str().unwrap_or("").chars().take(400).collect();
                let mut record = json!({
                    "stem": stem,
                    "topic": topic,
                    "chosen": entry["chosen"].as_str().unwrap_or(""),
                    "correct": entry["correct"].as_str().unwrap_or(""),
                    "why": why,
                    "ms": json_i64(&entry["ms"], 0),
                    "mock": entry["mock"].as_bool().unwrap_or(false),
                    "ts": now,
                });
                if let Some(options) = entry.get("options").and_then(|v| v.as_object()) {
                    let opts: serde_json::Map<String, Value> = options
                        .iter()
                        .map(|(k, v)| (k.clone(), json!(v.as_str().unwrap_or(""))))
                        .collect();
                    record["options"] = Value::Object(opts);
                }
                if let Some(explanation) = entry.get("explanation").and_then(|v| v.as_str()) {
                    let truncated: String = explanation.chars().take(2000).collect();
                    record["explanation"] = json!(truncated);
                }
                let mut entries = self
                    .get_config_optional::<Vec<Value>, _>("gmatErrorLog")
                    .unwrap_or_default();
                entries.push(record);
                let start = entries.len().saturating_sub(500);
                let trimmed = entries[start..].to_vec();
                self.gmat_put_config("gmatErrorLog", &Value::Array(trimmed))?;
                self.gmat_apply_repair(&topic, &why)?;
                String::new()
            }
            "gmatSetErrorTakeaway" => {
                let body = parse_body(body);
                let ts = json_i64(&body["ts"], 0);
                let takeaway = body.get("takeaway").cloned();
                if ts > 0 {
                    if let Some(takeaway) = takeaway {
                        let mut entries = self
                            .get_config_optional::<Vec<Value>, _>("gmatErrorLog")
                            .unwrap_or_default();
                        let mut found = false;
                        for entry in &mut entries {
                            if json_i64(&entry["ts"], 0) == ts {
                                if let Value::Object(map) = entry {
                                    map.insert("ai_takeaway".to_string(), takeaway);
                                    found = true;
                                }
                                break;
                            }
                        }
                        if found {
                            self.gmat_put_config("gmatErrorLog", &Value::Array(entries))?;
                        }
                    }
                }
                String::new()
            }
            "gmatErrorLog" => {
                let entries = self
                    .get_config_optional::<Vec<Value>, _>("gmatErrorLog")
                    .unwrap_or_default();
                let reversed: Vec<Value> = entries.into_iter().rev().collect();
                json!({ "entries": reversed }).to_string()
            }
            "gmatMockQuestions" => {
                let pool_notes = self.gmat_question_pool(resource_dir)?;
                let mut seen_nids: HashSet<i64> = HashSet::new();
                {
                    let mut stmt = self
                        .storage
                        .db
                        .prepare("select distinct c.nid from cards c join revlog r on r.cid = c.id")?;
                    let rows = stmt.query_map([], |r| r.get::<_, i64>(0))?;
                    for row in rows {
                        seen_nids.insert(row?);
                    }
                }
                let mut pool: Vec<Value> = pool_notes
                    .iter()
                    .map(|q| q.mock_json(q.nid > 0 && seen_nids.contains(&q.nid)))
                    .collect();
                let mut rng = rand::rng();
                pool.shuffle(&mut rng);
                // unseen first so the client's adaptive picker prefers held-out items
                pool.sort_by_key(|q| q["seen"].as_bool().unwrap_or(false));
                pool.truncate(200);
                json!({
                    "pool": pool,
                    "count": 21,
                    "seconds": 45 * 60,
                    "target_ms": 128_000,
                })
                .to_string()
            }
            "gmatTopicQuestions" => {
                // topic-scoped practice pool in the mock-pool shape, filtered to
                // one Topic (unseen first). Fixed bank; `n` caps the session.
                let body = parse_body(body);
                let topic = body["topic"].as_str().unwrap_or("");
                let n = json_i64(&body["n"], 10).clamp(1, 50) as usize;
                let pool_notes = self.gmat_question_pool(resource_dir)?;
                let mut seen_nids: HashSet<i64> = HashSet::new();
                {
                    let mut stmt = self
                        .storage
                        .db
                        .prepare("select distinct c.nid from cards c join revlog r on r.cid = c.id")?;
                    let rows = stmt.query_map([], |r| r.get::<_, i64>(0))?;
                    for row in rows {
                        seen_nids.insert(row?);
                    }
                }
                let mut pool: Vec<Value> = pool_notes
                    .iter()
                    .filter(|q| topic.is_empty() || q.topic == topic)
                    .map(|q| q.mock_json(q.nid > 0 && seen_nids.contains(&q.nid)))
                    .collect();
                let mut rng = rand::rng();
                pool.shuffle(&mut rng);
                // unseen first so a fresh session prefers held-out items
                pool.sort_by_key(|q| q["seen"].as_bool().unwrap_or(false));
                pool.truncate(n);
                let count = pool.len();
                json!({
                    "pool": pool,
                    "count": count,
                    "seconds": 45 * 60,
                    "target_ms": 128_000,
                })
                .to_string()
            }
            "gmatMilestoneQuestions" => {
                // milestone pool (mock-pool shape) MIXED across LEARNED topics
                // (fallback: all topics), unseen first; the client's adaptive
                // picker mixes topics from this pool.
                let body = parse_body(body);
                let n = json_i64(&body["n"], GMAT_MILESTONE_N).clamp(1, GMAT_MILESTONE_N_MAX)
                    as usize;
                let learned: HashSet<String> = self
                    .get_config_optional::<Value, _>("gmatLearned")
                    .filter(Value::is_object)
                    .and_then(|v| v.as_object().map(|o| o.keys().cloned().collect()))
                    .unwrap_or_default();
                let pool_notes = self.gmat_question_pool(resource_dir)?;
                let mut seen_nids: HashSet<i64> = HashSet::new();
                {
                    let mut stmt = self
                        .storage
                        .db
                        .prepare("select distinct c.nid from cards c join revlog r on r.cid = c.id")?;
                    let rows = stmt.query_map([], |r| r.get::<_, i64>(0))?;
                    for row in rows {
                        seen_nids.insert(row?);
                    }
                }
                let build = |restrict: &HashSet<String>| -> Vec<Value> {
                    pool_notes
                        .iter()
                        .filter(|q| restrict.is_empty() || restrict.contains(&q.topic))
                        .map(|q| q.mock_json(q.nid > 0 && seen_nids.contains(&q.nid)))
                        .collect()
                };
                let mut pool = build(&learned);
                if pool.is_empty() {
                    pool = build(&HashSet::new());
                }
                let mut rng = rand::rng();
                pool.shuffle(&mut rng);
                pool.sort_by_key(|q| q["seen"].as_bool().unwrap_or(false));
                pool.truncate(200);
                let count = n.min(pool.len());
                json!({
                    "pool": pool,
                    "count": count,
                    "seconds": n as i64 * (GMAT_TARGET_MS / 1000),
                    "target_ms": 128_000,
                })
                .to_string()
            }
            "gmatSubmitMock" => self.gmat_submit_mock(&parse_body(body), now)?,
            "gmatSubmitQuiz" => self.gmat_submit_quiz(&parse_body(body), now)?,
            "gmatTests" => {
                // practice-test catalog grouped by year, merged with taken status
                let index = gmat_read_tests_index(resource_dir);
                let taken = self
                    .get_config_optional::<Value, _>("gmatTestsTaken")
                    .filter(Value::is_object)
                    .unwrap_or_else(|| json!({}));
                let taken_obj = taken.as_object();
                let mut years_out = serde_json::Map::new();
                if let Some(years) = index["years"].as_object() {
                    for (group_key, forms) in years {
                        let mut out_forms: Vec<Value> = Vec::new();
                        if let Some(arr) = forms.as_array() {
                            for f in arr {
                                let fid = f["id"].as_str().unwrap_or("");
                                let status = taken_obj.and_then(|o| o.get(fid));
                                out_forms.push(json!({
                                    "id": fid,
                                    "year": gmat_form_year(f, group_key),
                                    "label": f["label"].as_str().unwrap_or(fid),
                                    "count": f.get("count").cloned().unwrap_or(json!(21)),
                                    "topics": f.get("topics").cloned().unwrap_or_else(|| json!({})),
                                    "sources": f.get("sources").cloned().unwrap_or_else(|| json!([])),
                                    "taken": status.is_some(),
                                    "accuracy": status.and_then(|s| s.get("accuracy")).cloned().unwrap_or(Value::Null),
                                    "q": status.and_then(|s| s.get("q")).cloned().unwrap_or(Value::Null),
                                    "ts": status.and_then(|s| s.get("ts")).cloned().unwrap_or(Value::Null),
                                }));
                            }
                        }
                        years_out.insert(group_key.clone(), Value::Array(out_forms));
                    }
                }
                json!({ "years": Value::Object(years_out) }).to_string()
            }
            "gmatTestQuestions" => {
                // one form's questions in the mock-pool shape, in fixed item order
                let body = parse_body(body);
                let form_id = body["id"].as_str().unwrap_or("");
                match gmat_read_test_form(resource_dir, form_id) {
                    Some(form) => {
                        let empty: Vec<Value> = Vec::new();
                        let items = form["items"].as_array().unwrap_or(&empty);
                        let pool: Vec<Value> = items
                            .iter()
                            .map(|it| {
                                let difficulty = it["difficulty"]
                                    .as_str()
                                    .filter(|s| !s.is_empty())
                                    .unwrap_or("medium");
                                json!({
                                    "stem": it["stem"].as_str().unwrap_or(""),
                                    "options": it.get("options").cloned().unwrap_or_else(|| json!({})),
                                    "correct": it["correct"].as_str().unwrap_or(""),
                                    "topic": it["topic"].as_str().unwrap_or(""),
                                    "difficulty": difficulty,
                                    "seen": false,
                                })
                            })
                            .collect();
                        let count = pool.len();
                        json!({
                            "pool": pool,
                            "count": count,
                            "seconds": form.get("seconds").cloned().unwrap_or(json!(45 * 60)),
                            "target_ms": form.get("target_ms").cloned().unwrap_or(json!(128_000)),
                            "form_id": form["id"].as_str().unwrap_or(form_id),
                            "label": form["label"].as_str().unwrap_or(""),
                        })
                        .to_string()
                    }
                    None => json!({
                        "pool": [],
                        "count": 21,
                        "seconds": 45 * 60,
                        "target_ms": 128_000,
                    })
                    .to_string(),
                }
            }
            // Desktop-only bridges (open Anki's stats/deck browser, trigger the
            // desktop sync). No mobile equivalent - the phone syncs via
            // gmat_sync_collection_at and has its own stats/decks UI.
            "gmatOpenStats" | "gmatOpenDecks" | "gmatSyncNow" => json!({ "ok": true }).to_string(),
            // Cross-device state sync (Firestore): export/import/reset ONLY the
            // GMATWiz config JSON, never the whole collection. Same shape the web
            // client + desktop mediasrv use: { "state": { <key>: <val|null>, ... } }.
            "gmatExportState" => {
                let mut state = serde_json::Map::new();
                for key in GMAT_STATE_KEYS {
                    state.insert(
                        (*key).to_string(),
                        self.get_config_optional::<Value, _>(*key)
                            .unwrap_or(Value::Null),
                    );
                }
                state.insert(
                    "topicAwareScheduling".to_string(),
                    json!(self
                        .get_config_optional::<bool, _>("topicAwareScheduling")
                        .unwrap_or(false)),
                );
                json!({ "state": Value::Object(state) }).to_string()
            }
            "gmatImportState" => {
                let body = parse_body(body);
                let state = &body["state"];
                for key in GMAT_STATE_KEYS {
                    let value = &state[*key];
                    if !value.is_null() {
                        self.gmat_put_config(key, value)?;
                    }
                }
                if let Some(b) = state["topicAwareScheduling"].as_bool() {
                    self.set_config_bool(BoolKey::TopicAwareScheduling, b, false)?;
                }
                json!({ "ok": true }).to_string()
            }
            "gmatResetState" => {
                for key in GMAT_STATE_KEYS {
                    self.remove_config(key)?;
                }
                self.set_config_bool(BoolKey::TopicAwareScheduling, false, false)?;
                json!({ "ok": true }).to_string()
            }
            _ => return Option::<String>::None.or_invalid(format!("unknown gmat endpoint: {name}")),
        };
        Ok(out)
    }
}

// --- Sync (shared by desktop + mobile) ---------------------------------------
// Desktop already has Anki's full sync built in. For mobile we expose the same
// engine sync in one call. A full sync reopens the collection, which the Backend
// manages, so sync goes through a Backend rather than a bare Collection.

impl crate::backend::Backend {
    /// Log in, then sync against `endpoint`. On a first or divergent sync the
    /// server requires a full sync; we resolve it in the caller's chosen
    /// direction (`prefer_upload`). Returns a small JSON status.
    pub fn gmat_sync(
        &self,
        endpoint: &str,
        username: &str,
        password: &str,
        prefer_upload: bool,
    ) -> Result<String> {
        use anki_proto::sync::sync_collection_response::ChangesRequired;

        use crate::services::BackendSyncService;

        let auth = self.sync_login(anki_proto::sync::SyncLoginRequest {
            username: username.into(),
            password: password.into(),
            endpoint: Some(endpoint.into()),
        })?;
        let out = self.sync_collection(anki_proto::sync::SyncCollectionRequest {
            auth: Some(auth.clone()),
            sync_media: false,
        })?;
        let full = |upload: bool| -> Result<&'static str> {
            self.full_upload_or_download(anki_proto::sync::FullUploadOrDownloadRequest {
                auth: Some(auth.clone()),
                upload,
                server_usn: None,
            })?;
            Ok(if upload { "full_upload" } else { "full_download" })
        };
        // When the server dictates a single possible direction (e.g. the server
        // is empty -> upload is the only option), obey it rather than the
        // caller's preference, so a first sync can never silently wipe a side.
        let action =
            match ChangesRequired::try_from(out.required).unwrap_or(ChangesRequired::NoChanges) {
                ChangesRequired::NoChanges => "no_changes",
                ChangesRequired::NormalSync => "normal_sync",
                ChangesRequired::FullDownload => full(false)?,
                ChangesRequired::FullUpload => full(true)?,
                _ => full(prefer_upload)?,
            };
        Ok(json!({ "ok": true, "action": action }).to_string())
    }
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn time_flags_separate_careless_from_fragile() {
        // fast + wrong = careless signal
        assert_eq!(gmat_time_flag(30_000, false), Some("rushed_wrong"));
        // slow + correct = fragile knowledge
        assert_eq!(gmat_time_flag(200_000, true), Some("slow_correct"));
        // on-pace answers and untimed rows carry no flag
        assert_eq!(gmat_time_flag(100_000, true), None);
        assert_eq!(gmat_time_flag(100_000, false), None);
        assert_eq!(gmat_time_flag(0, false), None);
        // slow + wrong is a plain miss (not "rushed"), fast + correct is fine
        assert_eq!(gmat_time_flag(200_000, false), None);
        assert_eq!(gmat_time_flag(30_000, true), None);
    }

    #[test]
    fn accuracy_to_quant_anchors_and_clamps() {
        assert_eq!(gmat_accuracy_to_quant(0.40), 70);
        assert_eq!(gmat_accuracy_to_quant(0.90), 88);
        assert_eq!(gmat_accuracy_to_quant(0.0), 60); // clamped floor
        assert_eq!(gmat_accuracy_to_quant(1.0), 90); // clamped ceiling
    }
}

/// Open the collection at `col_path`, sync it against `endpoint`, then close it.
/// The caller must NOT hold the collection open (SQLite is single-writer): the
/// iOS app closes its review collection, calls this, then reopens.
pub fn gmat_sync_collection_at(
    col_path: &str,
    endpoint: &str,
    username: &str,
    password: &str,
    prefer_upload: bool,
) -> Result<String> {
    use anki_i18n::I18n;

    use crate::backend::Backend;
    use crate::services::BackendCollectionService;

    let base = col_path.trim_end_matches(".anki2");
    let backend = Backend::new(I18n::template_only(), false);
    backend.open_collection(anki_proto::collection::OpenCollectionRequest {
        collection_path: col_path.into(),
        media_folder_path: format!("{base}.media"),
        media_db_path: format!("{base}.media.db2"),
    })?;
    let result = backend.gmat_sync(endpoint, username, password, prefer_upload);
    let _ = backend.close_collection(anki_proto::collection::CloseCollectionRequest {
        downgrade_to_schema11: false,
    });
    result
}
