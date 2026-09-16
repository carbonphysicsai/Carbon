export const PUBLIC_RELEASE_STATUS = "APPROVED_PUBLIC";
export const STAGING_RELEASE_STATUS = "STAGING_REVIEWED";

const validDate = (value) => typeof value === "string" && Number.isFinite(Date.parse(value));
const expired = (value, nowMs) => !validDate(value) || Date.parse(value) <= nowMs;

export const evaluateRelease = (knowledge, { mode = "production", now = new Date() } = {}) => {
  const reasons = [];
  const nowMs = now instanceof Date ? now.getTime() : Number(now);
  const release = knowledge?.release;
  if (knowledge?.schema_version !== 2) reasons.push("unsupported_schema_version");
  if (!release || typeof release !== "object") reasons.push("missing_release");
  if (!knowledge?.knowledge_version) reasons.push("missing_knowledge_version");
  if (!validDate(release?.source_release_date)) reasons.push("missing_source_release_date");
  if (expired(release?.expires_at, nowMs)) reasons.push("release_expired_or_invalid");
  if (release?.withdrawn_at) reasons.push("release_withdrawn");
  if (!Number.isSafeInteger(release?.withdrawal_epoch) || release.withdrawal_epoch < 1) reasons.push("invalid_withdrawal_epoch");
  if (mode === "production") {
    if (release?.status !== PUBLIC_RELEASE_STATUS) reasons.push("release_not_approved_public");
    if (release?.public_activation_allowed !== true) reasons.push("public_activation_not_allowed");
  } else if (mode === "staging") {
    if (![STAGING_RELEASE_STATUS, PUBLIC_RELEASE_STATUS].includes(release?.status)) reasons.push("release_not_staging_reviewed");
    if (release?.staging_activation_allowed !== true) reasons.push("staging_activation_not_allowed");
  } else {
    reasons.push("invalid_release_mode");
  }

  const sources = new Map();
  const ineligibleSources = new Map();
  for (const source of knowledge?.sources ?? []) {
    if (!source?.id || sources.has(source.id)) reasons.push("duplicate_or_missing_source_id");
    else sources.set(source.id, source);
    const sourceIssues = [];
    if (source?.publication_status !== "REVIEWED_PUBLIC_EXISTING") sourceIssues.push("not_releasable");
    if (source?.withdrawn_at) sourceIssues.push("withdrawn");
    if (!source?.revision || !source?.sha256 || source?.integrity_status !== "MATCHED_AT_BUILD") sourceIssues.push("integrity_unverified");
    try {
      const url = new URL(source?.url);
      if (url.protocol !== "https:") sourceIssues.push("invalid_url");
    } catch {
      sourceIssues.push("invalid_url");
    }
    if (sourceIssues.length) ineligibleSources.set(source?.id, sourceIssues);
  }
  if (!sources.size) reasons.push("missing_sources");

  const cards = new Map();
  const eligibleCardIds = [];
  const ineligibleCards = {};
  for (const card of knowledge?.cards ?? []) {
    const cardIssues = [];
    if (!card?.id || cards.has(card.id)) reasons.push("duplicate_or_missing_card_id");
    else cards.set(card.id, card);
    if (card?.publication_status !== "REVIEWED_PUBLIC_EXISTING") cardIssues.push("not_releasable");
    if (card?.withdrawn_at) cardIssues.push("withdrawn");
    if (expired(card?.expires_at, nowMs)) cardIssues.push("expired_or_invalid");
    if (!Array.isArray(card?.passages) || !card.passages.length) cardIssues.push("missing_passages");
    const sourceIds = new Set();
    for (const passage of card?.passages ?? []) {
      if (!passage?.id || !passage?.text || !passage?.source_id) cardIssues.push("invalid_passage");
      sourceIds.add(passage?.source_id);
    }
    if ([...sourceIds].some((sourceId) => !sources.has(sourceId))) cardIssues.push("unknown_source");
    if ([...sourceIds].some((sourceId) => ineligibleSources.has(sourceId))) cardIssues.push("source_ineligible");
    if (!cardIssues.length) {
      eligibleCardIds.push(card.id);
    } else ineligibleCards[card?.id ?? "unknown"] = [...new Set(cardIssues)].sort();
  }
  if (!cards.size) reasons.push("missing_cards");
  if (!eligibleCardIds.length) reasons.push("no_eligible_cards");
  return {
    valid: reasons.length === 0,
    mode,
    reasons: [...new Set(reasons)].sort(),
    eligible_card_ids: eligibleCardIds.sort(),
    knowledge_version: knowledge?.knowledge_version ?? null,
    source_release_date: release?.source_release_date ?? null,
    expires_at: release?.expires_at ?? null,
    withdrawal_epoch: release?.withdrawal_epoch ?? null,
    ineligible_cards: ineligibleCards,
  };
};

export const eligibleCards = (knowledge, options) => {
  const status = evaluateRelease(knowledge, options);
  if (!status.valid) return { status, cards: [] };
  const ids = new Set(status.eligible_card_ids);
  return { status, cards: knowledge.cards.filter((card) => ids.has(card.id)) };
};
