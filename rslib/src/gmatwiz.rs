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
// GMAT Focus Quant pacing: 21 questions in 45 minutes ~= 128s per question.
const GMAT_TARGET_MS: i64 = 128_000;

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
        let timed: Vec<(i64, u8, i64)> = raw
            .into_iter()
            .filter(|(cid, _, _)| card_topics.contains_key(cid))
            .map(|(cid, ease, ms)| (cid, u8::from(ease >= 2), ms))
            .collect();
        let attempts: Vec<(i64, u8)> = timed.iter().map(|&(cid, ok, _)| (cid, ok)).collect();
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

        // Timing analytics over timed first-exposure attempts: separates
        // "fast but wrong" (careless) from "slow but correct" (fragile).
        let with_time: Vec<&(i64, u8, i64)> = timed.iter().filter(|(_, _, ms)| *ms > 0).collect();
        let timing = if with_time.is_empty() {
            serde_json::Value::Null
        } else {
            let n = with_time.len();
            let avg_ms = with_time.iter().map(|(_, _, ms)| ms).sum::<i64>() / n as i64;
            let rushed_wrong = with_time
                .iter()
                .filter(|(_, ok, ms)| gmat_time_flag(*ms, *ok == 1) == Some("rushed_wrong"))
                .count();
            let slow_correct = with_time
                .iter()
                .filter(|(_, ok, ms)| gmat_time_flag(*ms, *ok == 1) == Some("slow_correct"))
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
