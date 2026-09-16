import { evaluateRelease } from "../public/release-contract.js";
import { PublicApiError } from "./errors.mjs";
import { getModelProfile } from "./models.mjs";

export { PublicApiError } from "./errors.mjs";
export const MAX_QUESTION_LENGTH = 1200;
export const MAX_BODY_BYTES = 12_000;
export const MAX_PROVIDER_RESPONSE_BYTES = 96_000;
export const MAX_CONTINUATION_LENGTH = 4_000;
export const CONTINUATION_TTL_SECONDS = 900;
export const OWNER_MONTHLY_LIMIT_MICRO_USD = 50_000_000;
export const SHARED_LEDGER_AUTHORITY = "ask-carbon-provider-budget-v2";
export const STAGING_PRIVACY_MODE = "evaluation_public_synthetic_only";
export const PRODUCTION_PRIVACY_MODE = "approved_public_privacy_v1";

const encoder = new TextEncoder();
const decoder = new TextDecoder();
const STOP_WORDS = new Set(["a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "how", "i", "in", "is", "it", "of", "on", "or", "that", "the", "their", "this", "to", "was", "what", "when", "where", "which", "who", "why", "with", "you"]);

const stem = (word) => word.replace(/(?:ies|ing|ed|es|s)$/i, (ending) => ending === "ies" ? "y" : "");
export const tokens = (value) => (String(value ?? "").toLowerCase().match(/[a-z0-9]+/g) ?? [])
  .map(stem)
  .filter((word) => word.length > 1 && !STOP_WORDS.has(word));
const tokenSet = (value) => new Set(tokens(value));
const parsePositiveInteger = (value) => {
  if (!/^[1-9]\d*$/.test(String(value ?? ""))) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
};
export { parsePositiveInteger };
export const splitCsv = (value) => String(value ?? "").split(",").map((item) => item.trim()).filter(Boolean);

const requiredEnvironment = [
  "ASK_CARBON_ACTIVATION", "ASK_CARBON_RUNTIME_MODE", "ASK_CARBON_APPROVED_ORIGINS",
  "ASK_CARBON_APPROVED_MODEL_CONFIGS", "ASK_CARBON_MODEL_CONFIG_ID",
  "ASK_CARBON_OPENAI_API_KEY", "ASK_CARBON_CONTINUATION_SIGNING_SECRET",
  "ASK_CARBON_PRIVACY_MODE", "ASK_CARBON_EDGE_ABUSE_POLICY_ID",
  "ASK_CARBON_LEDGER_AUTHORITY_ID", "ASK_CARBON_ENVIRONMENT",
  "ASK_CARBON_OPERATIONAL_SCOPE_ID", "ASK_CARBON_OPERATIONAL_SCOPE_LIMIT_MICRO_USD",
  "ASK_CARBON_MONTHLY_LIMIT_MICRO_USD", "ASK_CARBON_DAILY_REQUEST_LIMIT",
  "ASK_CARBON_MAX_CONCURRENCY", "ASK_CARBON_CLIENT_REQUESTS_PER_HOUR",
  "ASK_CARBON_CLIENT_COUNTER_RETENTION_MS", "ASK_CARBON_MAX_INPUT_TOKENS",
  "ASK_CARBON_MAX_OUTPUT_TOKENS", "ASK_CARBON_PROVIDER_TIMEOUT_MS",
];

export const activationStatus = (env, knowledge, now = new Date()) => {
  const reasons = [];
  if (env.ASK_CARBON_ACTIVATION !== "enabled") reasons.push("activation_disabled");
  for (const key of requiredEnvironment) if (!env[key]) reasons.push(`missing_${key.toLowerCase()}`);
  if (!env.ASK_CARBON_USAGE_LEDGER?.idFromName || !env.ASK_CARBON_USAGE_LEDGER?.get) reasons.push("missing_usage_ledger_binding");
  const mode = env.ASK_CARBON_RUNTIME_MODE;
  const release = evaluateRelease(knowledge, { mode: mode === "production" ? "production" : "staging", now });
  reasons.push(...release.reasons);
  if (!['staging', 'production'].includes(mode)) reasons.push("invalid_runtime_mode");
  if (mode === "staging") {
    if (env.ASK_CARBON_PRIVACY_MODE !== STAGING_PRIVACY_MODE) reasons.push("invalid_staging_privacy_mode");
    if (typeof env.ASK_CARBON_EDGE_ACCESS_POLICY_ID !== "string" || !env.ASK_CARBON_EDGE_ACCESS_POLICY_ID || env.ASK_CARBON_EDGE_ACCESS_POLICY_ID.startsWith("OWNER_DECISION_REQUIRED")) reasons.push("missing_private_staging_access_policy");
  }
  if (mode === "production" && env.ASK_CARBON_PRIVACY_MODE !== PRODUCTION_PRIVACY_MODE) reasons.push("public_privacy_not_accepted");
  if (typeof env.ASK_CARBON_EDGE_ABUSE_POLICY_ID !== "string" || env.ASK_CARBON_EDGE_ABUSE_POLICY_ID.startsWith("OWNER_DECISION_REQUIRED")) reasons.push("missing_edge_abuse_policy");
  const profile = getModelProfile(env.ASK_CARBON_MODEL_CONFIG_ID);
  if (!profile) reasons.push("unsupported_model_config");
  if (env.ASK_CARBON_MODEL_CONFIG_ID && !splitCsv(env.ASK_CARBON_APPROVED_MODEL_CONFIGS).includes(env.ASK_CARBON_MODEL_CONFIG_ID)) reasons.push("model_config_not_approved");
  if (env.ASK_CARBON_LEDGER_AUTHORITY_ID !== SHARED_LEDGER_AUTHORITY) reasons.push("unverified_shared_ledger_authority");
  if (parsePositiveInteger(env.ASK_CARBON_MONTHLY_LIMIT_MICRO_USD) !== OWNER_MONTHLY_LIMIT_MICRO_USD) reasons.push("invalid_monthly_limit");
  const scopeLimit = parsePositiveInteger(env.ASK_CARBON_OPERATIONAL_SCOPE_LIMIT_MICRO_USD);
  if (!scopeLimit || scopeLimit > OWNER_MONTHLY_LIMIT_MICRO_USD) reasons.push("invalid_scope_limit");
  for (const key of ["ASK_CARBON_DAILY_REQUEST_LIMIT", "ASK_CARBON_MAX_CONCURRENCY", "ASK_CARBON_CLIENT_REQUESTS_PER_HOUR", "ASK_CARBON_CLIENT_COUNTER_RETENTION_MS", "ASK_CARBON_MAX_INPUT_TOKENS", "ASK_CARBON_MAX_OUTPUT_TOKENS", "ASK_CARBON_PROVIDER_TIMEOUT_MS"]) {
    if (!parsePositiveInteger(env[key])) reasons.push(`invalid_${key.toLowerCase()}`);
  }
  if (!splitCsv(env.ASK_CARBON_APPROVED_ORIGINS).length) reasons.push("no_approved_origins");
  return { ...release, active: reasons.length === 0, reasons: [...new Set(reasons)].sort(), model_config_id: profile?.config_id ?? null };
};

export const normalizeOrigin = (value) => {
  try {
    const url = new URL(value);
    if (!/^https?:$/.test(url.protocol) || url.username || url.password || url.pathname !== "/" || url.search || url.hash) return null;
    return url.origin;
  } catch { return null; }
};
export const assertAllowedOrigin = (request, env) => {
  const origin = normalizeOrigin(request.headers.get("origin"));
  const allowed = splitCsv(env.ASK_CARBON_APPROVED_ORIGINS).map(normalizeOrigin).filter(Boolean);
  if (!origin || !allowed.includes(origin)) throw new PublicApiError(403, "origin_not_allowed", "This request origin is not allowed.");
  return origin;
};
export const corsHeaders = (origin) => ({
  "access-control-allow-origin": origin,
  "access-control-allow-methods": "POST, OPTIONS",
  "access-control-allow-headers": "content-type",
  "access-control-max-age": "600",
  vary: "Origin",
});

export const validateRequestBody = (value) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new PublicApiError(400, "invalid_request", "The request body must be an object.");
  if (Object.keys(value).some((key) => !["question", "continuation"].includes(key))) throw new PublicApiError(400, "invalid_request", "The request contains unsupported fields.");
  if (typeof value.question !== "string") throw new PublicApiError(400, "invalid_question", "A question is required.");
  const question = value.question.trim();
  if (!question || question.length > MAX_QUESTION_LENGTH) throw new PublicApiError(400, "invalid_question", `Questions must contain 1 to ${MAX_QUESTION_LENGTH} characters.`);
  if (/(?:api[_ -]?key|private[_ -]?key|password|secret)\s*[:=]\s*\S+/i.test(question)) throw new PublicApiError(400, "possible_secret", "Please remove credentials or secrets before asking a public question.");
  if (value.continuation !== undefined && (typeof value.continuation !== "string" || !value.continuation || value.continuation.length > MAX_CONTINUATION_LENGTH)) {
    throw new PublicApiError(400, "invalid_continuation", "The conversation continuation is invalid.");
  }
  return { question, continuation: value.continuation ?? null };
};

const directCardScore = (card, question) => {
  const normalized = question.trim().toLowerCase();
  if ((card.questions ?? [card.question]).some((item) => item.toLowerCase() === normalized)) return 100;
  const query = tokenSet(question);
  const cardTerms = [...tokens((card.questions ?? [card.question]).join(" ")), ...tokens((card.keywords ?? []).join(" ")), ...tokens(card.topic)];
  return cardTerms.reduce((score, term) => score + (query.has(term) ? 2 : 0), 0);
};
const needsTopicContext = (question) => /\b(those|they|them|their|it|that|this|these|former|latter)\b/i.test(question) || tokens(question).length <= 2;

export const selectCards = (knowledge, question, { continuation = null, limit = 6, minScore = 2, eligibleCardIds = null } = {}) => {
  const eligible = eligibleCardIds ? new Set(eligibleCardIds) : null;
  const candidates = (knowledge.cards ?? []).filter((card) => !eligible || eligible.has(card.id));
  const direct = candidates.map((card) => ({ card, direct: directCardScore(card, question), context: 0 }));
  const bestDirect = Math.max(0, ...direct.map((item) => item.direct));
  const useContext = needsTopicContext(question) && bestDirect < 6 && Array.isArray(continuation?.card_ids);
  const priorIds = new Set(useContext ? continuation.card_ids : []);
  for (const item of direct) {
    if (priorIds.has(item.card.id)) item.context += 3;
    const related = new Set(item.card.related ?? []);
    for (const id of priorIds) if (related.has(id)) item.context += 2;
  }
  const ranked = direct
    .map((item) => ({ ...item, score: item.direct + item.context }))
    .filter((item) => item.score >= minScore)
    .sort((left, right) => right.score - left.score || right.direct - left.direct || left.card.id.localeCompare(right.card.id));
  return { kind: ranked.length ? "match" : "no_evidence", cards: ranked.slice(0, limit).map((item) => item.card), used_context: useContext, top_score: ranked[0]?.score ?? 0 };
};

const base64UrlEncode = (bytes) => {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
};
const base64UrlDecode = (value) => {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
};
const hmacKey = (secret) => crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
export const signContinuation = async (payload, secret) => {
  const encoded = base64UrlEncode(encoder.encode(JSON.stringify(payload)));
  const signature = await crypto.subtle.sign("HMAC", await hmacKey(secret), encoder.encode(encoded));
  return `${encoded}.${base64UrlEncode(new Uint8Array(signature))}`;
};
export const verifyContinuation = async (token, secret, knowledge, nowSeconds = Math.floor(Date.now() / 1000)) => {
  try {
    if (typeof token !== "string" || token.split(".").length !== 2) throw new Error("shape");
    const [encoded, signature] = token.split(".");
    const valid = await crypto.subtle.verify("HMAC", await hmacKey(secret), base64UrlDecode(signature), encoder.encode(encoded));
    if (!valid) throw new Error("signature");
    const payload = JSON.parse(decoder.decode(base64UrlDecode(encoded)));
    if (payload.v !== 2 || payload.knowledge_version !== knowledge.knowledge_version ||
        payload.withdrawal_epoch !== knowledge.release.withdrawal_epoch ||
        !Number.isSafeInteger(payload.iat) || !Number.isSafeInteger(payload.exp) || payload.exp <= nowSeconds || payload.iat > nowSeconds + 5 ||
        !Array.isArray(payload.card_ids) || payload.card_ids.length > 6 || payload.card_ids.some((id) => typeof id !== "string")) throw new Error("payload");
    return payload;
  } catch {
    throw new PublicApiError(400, "invalid_continuation", "The conversation continuation is invalid or expired.");
  }
};
export const makeContinuation = async ({ cards, knowledge, secret, nowSeconds }) => signContinuation({
  v: 2,
  knowledge_version: knowledge.knowledge_version,
  withdrawal_epoch: knowledge.release.withdrawal_epoch,
  card_ids: cards.map((card) => card.id).slice(0, 6),
  iat: nowSeconds,
  exp: nowSeconds + CONTINUATION_TTL_SECONDS,
}, secret);

export const answerSchema = {
  type: "object",
  additionalProperties: false,
  required: ["status", "answer", "claims", "follow_up"],
  properties: {
    status: { type: "string", enum: ["supported"] },
    answer: { type: "string", minLength: 1, maxLength: 1800 },
    claims: {
      type: "array", minItems: 1, maxItems: 8,
      items: {
        type: "object", additionalProperties: false, required: ["text", "evidence_ids"],
        properties: {
          text: { type: "string", minLength: 1, maxLength: 500 },
          evidence_ids: { type: "array", minItems: 1, maxItems: 4, uniqueItems: true, items: { type: "string" } },
        },
      },
    },
    follow_up: { type: ["string", "null"], maxLength: 160 },
  },
};

const overlap = (claim, evidence) => {
  const claimTerms = [...new Set(tokens(claim))];
  const evidenceTerms = tokenSet(evidence);
  const hits = claimTerms.filter((term) => evidenceTerms.has(term)).length;
  return { hits, total: claimTerms.length, ratio: claimTerms.length ? hits / claimTerms.length : 0 };
};
const sensitiveClaim = /\b(paid customer|customer result|launched|live network|production[- ]qualified|scientifically qualified|security qualified|proven model performance|guaranteed return)\b/i;

export const validateProviderOutput = (value, cards) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned an invalid result.");
  const keys = Object.keys(value).sort();
  if (JSON.stringify(keys) !== JSON.stringify(["answer", "claims", "follow_up", "status"])) throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned unsupported fields.");
  if (value.status !== "supported" || typeof value.answer !== "string" || !value.answer.trim() || value.answer.length > 1800) throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned invalid answer text.");
  if (value.follow_up !== null && (typeof value.follow_up !== "string" || !value.follow_up.trim() || value.follow_up.length > 160)) throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned an invalid follow-up.");
  if (!Array.isArray(value.claims) || value.claims.length < 1 || value.claims.length > 8) throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned an invalid claim map.");
  const passages = new Map(cards.flatMap((card) => (card.passages ?? []).map((passage) => [passage.id, { ...passage, card_id: card.id }])));
  const usedPassages = new Set();
  for (const claim of value.claims) {
    if (!claim || typeof claim !== "object" || Array.isArray(claim) || Object.keys(claim).some((key) => !["text", "evidence_ids"].includes(key)) ||
        typeof claim.text !== "string" || !claim.text.trim() || claim.text.length > 500 ||
        !Array.isArray(claim.evidence_ids) || !claim.evidence_ids.length || claim.evidence_ids.length > 4 || new Set(claim.evidence_ids).size !== claim.evidence_ids.length) {
      throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned an invalid claim map.");
    }
    if (!value.answer.toLowerCase().includes(claim.text.trim().toLowerCase())) throw new PublicApiError(502, "unsupported_claim", "An answer claim was not bound to the answer text.");
    const evidence = claim.evidence_ids.map((id) => passages.get(id)).filter(Boolean);
    if (evidence.length !== claim.evidence_ids.length) throw new PublicApiError(502, "unknown_evidence", "The answer provider referenced evidence outside the retrieved context.");
    const evidenceText = evidence.map((item) => item.text).join(" ");
    const support = overlap(claim.text, evidenceText);
    if (support.hits < Math.min(3, support.total) || support.ratio < 0.45) throw new PublicApiError(502, "unsupported_claim", "A material answer claim was not supported by its cited passages.");
    if (sensitiveClaim.test(claim.text) && !sensitiveClaim.test(evidenceText)) throw new PublicApiError(502, "unsupported_sensitive_claim", "A sensitive status claim was not established by its cited passage.");
    for (const id of claim.evidence_ids) usedPassages.add(id);
  }
  const claimText = value.claims.map((claim) => claim.text.toLowerCase()).join(" ");
  for (const sentence of value.answer.split(/(?<=[.!?])\s+/).filter((item) => tokens(item).length >= 4)) {
    const support = overlap(sentence, claimText);
    if (support.ratio < 0.5) throw new PublicApiError(502, "unmapped_answer_claim", "The answer contained material text without a claim-to-evidence binding.");
  }
  const evidence = [...usedPassages].map((id) => ({ id, ...passages.get(id) }));
  return {
    status: "supported",
    answer: value.answer.trim(),
    claims: value.claims.map((claim) => ({ text: claim.text.trim(), evidence_ids: claim.evidence_ids })),
    follow_up: value.follow_up?.trim() || null,
    passage_ids: [...usedPassages],
    source_ids: [...new Set(evidence.map((item) => item.source_id))],
  };
};

export const detectOutOfScope = (question) => {
  if (/\b(token price|buy alpha|investment return|guaranteed return|financial advice)\b/i.test(question)) return "financial_advice";
  if (/\b(run (?:a )?(?:miner|mining job|evaluation)|submit (?:my|a) model|upload (?:my|our)|process (?:my|our) confidential)\b/i.test(question)) return "execution_or_private_work";
  return null;
};
export const publicSources = (knowledge, sourceIds) => sourceIds.map((id) => {
  const source = knowledge.sources.find((candidate) => candidate.id === id);
  if (!source) throw new PublicApiError(502, "unknown_source", "Approved evidence could not be resolved.");
  return { id: source.id, title: source.title, url: source.url, note: source.note, revision: source.revision, sections: source.sections };
});
export const extractResponseText = (body) => {
  if (typeof body?.output_text === "string" && body.output_text) return body.output_text;
  const fragments = [];
  for (const item of body?.output ?? []) {
    if (item?.type !== "message" || item?.role !== "assistant") continue;
    for (const content of item.content ?? []) if (content?.type === "output_text" && typeof content.text === "string") fragments.push(content.text);
  }
  return fragments.join("");
};
export const sha256Hex = async (value) => {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
};
