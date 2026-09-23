import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { evaluateRelease } from "../public/release-contract.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "../../..");
const DEFAULT_PATH = resolve(HERE, "../knowledge/public-knowledge.v1.json");
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");

// Reviewed thresholds, not flags. An expiry exists to force a content review, and
// the runtime only notices once it has passed, when the card simply stops
// answering. Surfacing it here, ahead of time, is what makes that review happen.
export const EXPIRY_WARN_DAYS = 30;
export const EXPIRY_FAIL_DAYS = 7;
const DAY_MS = 86_400_000;

// Returns the finding for one expiry, or null when it is outside both windows.
// An expired or unreadable expiry is not handled here: the release contract
// already reports it, and a card's is reported by the caller.
const expiryFinding = (expiresAt, nowMs) => {
  const remainingMs = Date.parse(expiresAt) - nowMs;
  if (!Number.isFinite(remainingMs) || remainingMs <= 0) return null;
  if (remainingMs <= EXPIRY_FAIL_DAYS * DAY_MS) return "error";
  if (remainingMs <= EXPIRY_WARN_DAYS * DAY_MS) return "warning";
  return null;
};

export const validateKnowledge = async (knowledge, { mode = "staging", now = new Date(), checkSourceBytes = true } = {}) => {
  const release = evaluateRelease(knowledge, { mode, now });
  const errors = [...release.reasons];
  const warnings = [];
  const nowMs = now instanceof Date ? now.getTime() : Number(now);
  const expiring = [];
  const noteExpiry = (scope, id, expiresAt) => {
    const finding = expiryFinding(expiresAt, nowMs);
    if (!finding) return;
    const code = finding === "error" ? `${scope}_expires_within_${EXPIRY_FAIL_DAYS}d` : `${scope}_expires_within_${EXPIRY_WARN_DAYS}d`;
    (finding === "error" ? errors : warnings).push(id ? `${code}:${id}` : code);
    expiring.push({ scope, id: id ?? null, expires_at: expiresAt, days_left: Math.floor((Date.parse(expiresAt) - nowMs) / DAY_MS), finding });
  };
  noteExpiry("release", null, knowledge.release?.expires_at);
  const sourceChecks = [];
  const passageIds = new Set();
  const sourceIds = new Set((knowledge.sources ?? []).map((source) => source.id));
  for (const source of knowledge.sources ?? []) {
    if (!source.note?.toLowerCase().includes("paraphras")) warnings.push(`source_note_not_marked_paraphrase:${source.id}`);
    if (checkSourceBytes && source.repo_path) {
      try {
        const observed = sha256(await readFile(resolve(REPO_ROOT, source.repo_path)));
        const matched = observed === source.sha256;
        sourceChecks.push({ source_id: source.id, repo_path: source.repo_path, expected_sha256: source.sha256, observed_sha256: observed, matched });
        if (!matched) errors.push(`source_changed:${source.id}`);
      } catch {
        errors.push(`source_unreadable:${source.id}`);
      }
    }
  }
  for (const card of knowledge.cards ?? []) {
    if (!Array.isArray(card.questions) || !card.questions.length || !card.answer || card.answer.length > 1800) errors.push(`invalid_card_text:${card.id}`);
    if (!Array.isArray(card.audiences) || !card.audiences.length || card.disclosure_class !== "PUBLIC" || !card.maturity || !card.scope_note) errors.push(`invalid_card_governance:${card.id}`);
    if (!Array.isArray(card.keywords) || !Array.isArray(card.related)) errors.push(`invalid_card_helpers:${card.id}`);
    if (!Array.isArray(card.passages) || !card.passages.length) errors.push(`missing_answer_basis:${card.id}`);
    // At runtime an expired card fails closed on its own and the rest keep
    // answering, which is right there and is exactly why nobody notices. Here it
    // is stale committed content and fails the check.
    const cardExpiry = card.expires_at;
    if (typeof cardExpiry !== "string" || !(Date.parse(cardExpiry) > nowMs)) errors.push(`card_expired_or_invalid:${card.id}`);
    else noteExpiry("card", card.id, cardExpiry);
    for (const passage of card.passages ?? []) {
      if (passageIds.has(passage.id)) errors.push(`duplicate_passage_id:${passage.id}`);
      passageIds.add(passage.id);
      if (passage.text.length > 900) errors.push(`passage_too_long:${passage.id}`);
      if (!sourceIds.has(passage.source_id)) errors.push(`unknown_answer_source:${card.id}:${passage.source_id}`);
    }
  }
  if (knowledge.candidate_review?.artifact_sha256 !== "ca1e23c3a77ec813c384d893358fe1fe1959edd5989068a5711b04e2821120cb" ||
      knowledge.candidate_review?.candidate_cards_received !== 31 || knowledge.candidate_review?.disposition !== "RECONCILED_AS_DRAFT_INPUT_NOT_COUNT_TARGET") {
    errors.push("candidate_review_provenance_invalid");
  }
  return {
    valid: errors.length === 0,
    mode,
    knowledge_version: knowledge.knowledge_version,
    card_count: knowledge.cards?.length ?? 0,
    source_count: knowledge.sources?.length ?? 0,
    eligible_card_count: release.eligible_card_ids.length,
    errors: [...new Set(errors)].sort(),
    warnings: [...new Set(warnings)].sort(),
    expiring: expiring.sort((a, b) => a.expires_at.localeCompare(b.expires_at) || String(a.id).localeCompare(String(b.id))),
    source_checks: sourceChecks,
  };
};

const main = async () => {
  const args = process.argv.slice(2);
  const mode = args.includes("--production") ? "production" : "staging";
  const pathArgument = args.find((argument) => !argument.startsWith("--"));
  const knowledge = JSON.parse(await readFile(resolve(pathArgument ?? DEFAULT_PATH), "utf8"));
  const result = await validateKnowledge(knowledge, { mode });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.valid) process.exitCode = 1;
};

if (process.argv[1] === fileURLToPath(import.meta.url)) main();
