import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_PATH = resolve(HERE, "../knowledge/public-knowledge.v1.json");

export const validateKnowledge = (knowledge, { production = false, now = new Date() } = {}) => {
  const errors = [];
  const warnings = [];
  if (knowledge.schema_version !== 1) errors.push("unsupported_schema_version");
  if (!knowledge.knowledge_version) errors.push("missing_knowledge_version");
  if (!Array.isArray(knowledge.sources) || !knowledge.sources.length) errors.push("missing_sources");
  if (!Array.isArray(knowledge.cards) || !knowledge.cards.length) errors.push("missing_cards");
  const sources = new Map();
  for (const source of knowledge.sources ?? []) {
    if (!source.id || sources.has(source.id)) errors.push("duplicate_or_missing_source_id");
    sources.set(source.id, source);
    try {
      const url = new URL(source.url);
      if (url.protocol !== "https:") errors.push(`non_https_source:${source.id}`);
    } catch {
      errors.push(`invalid_source_url:${source.id}`);
    }
    if (!source.note?.toLowerCase().includes("paraphras")) warnings.push(`source_note_not_marked_paraphrase:${source.id}`);
  }
  const cardIds = new Set();
  for (const card of knowledge.cards ?? []) {
    if (!card.id || cardIds.has(card.id)) errors.push("duplicate_or_missing_card_id");
    cardIds.add(card.id);
    if (!card.question || !card.answer || card.answer.length > 1600) errors.push(`invalid_card_text:${card.id}`);
    if (!Array.isArray(card.source_ids) || !card.source_ids.length) errors.push(`missing_card_sources:${card.id}`);
    for (const sourceId of card.source_ids ?? []) if (!sources.has(sourceId)) errors.push(`unknown_card_source:${card.id}:${sourceId}`);
    if (!Array.isArray(card.follow_ups) || !Array.isArray(card.keywords)) errors.push(`invalid_card_helpers:${card.id}`);
  }
  const review = knowledge.candidate_card_review;
  if (review?.expected_count !== 31 || review?.received_count !== 0 || review?.status !== "BLOCKED_MISSING_CANDIDATE_PACKAGE") {
    warnings.push("candidate_card_review_state_changed");
  } else {
    warnings.push("31_candidate_cards_not_received_or_reviewed");
  }
  if (production) {
    if (knowledge.release_status !== "APPROVED_PUBLIC") errors.push("knowledge_not_approved_for_production");
    if (!knowledge.source_release_date) errors.push("missing_source_release_date");
    if (!knowledge.expires_at || !Number.isFinite(Date.parse(knowledge.expires_at)) || Date.parse(knowledge.expires_at) <= now.getTime()) {
      errors.push("missing_or_expired_release");
    }
    if (review?.received_count !== review?.expected_count) errors.push("candidate_card_review_incomplete");
  } else if (knowledge.release_status !== "DRAFT_NOT_APPROVED") {
    warnings.push("preview_release_status_is_not_draft");
  }
  return { valid: errors.length === 0, production, card_count: knowledge.cards?.length ?? 0, source_count: sources.size, errors, warnings };
};

const main = async () => {
  const argumentsList = process.argv.slice(2);
  const production = argumentsList.includes("--production");
  const pathArgument = argumentsList.find((argument) => !argument.startsWith("--"));
  const knowledge = JSON.parse(await readFile(resolve(pathArgument ?? DEFAULT_PATH), "utf8"));
  const result = validateKnowledge(knowledge, { production });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.valid) process.exitCode = 1;
};

if (process.argv[1] === fileURLToPath(import.meta.url)) main();
