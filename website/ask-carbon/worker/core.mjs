const encoder = new TextEncoder();
const decoder = new TextDecoder();

export const MAX_QUESTION_LENGTH = 1200;
export const MAX_CONTEXT_TURNS = 4;
export const MAX_TURN_TEXT_LENGTH = 1600;
export const MAX_BODY_BYTES = 12_000;
export const CONTEXT_TTL_SECONDS = 180;

const ACTIVATION_REQUIREMENTS = [
  "ASK_CARBON_ACTIVATION",
  "ASK_CARBON_APPROVED_ORIGINS",
  "ASK_CARBON_APPROVED_MODELS",
  "ASK_CARBON_MODEL",
  "ASK_CARBON_OPENAI_API_KEY",
  "ASK_CARBON_CONTEXT_SIGNING_SECRET",
  "ASK_CARBON_INPUT_USD_PER_MILLION",
  "ASK_CARBON_OUTPUT_USD_PER_MILLION",
  "ASK_CARBON_DAILY_REQUEST_LIMIT",
  "ASK_CARBON_DAILY_COST_MICRO_USD_LIMIT",
  "ASK_CARBON_MAX_CONCURRENCY",
  "ASK_CARBON_CLIENT_REQUESTS_PER_HOUR",
  "ASK_CARBON_MAX_INPUT_TOKENS",
  "ASK_CARBON_MAX_OUTPUT_TOKENS",
  "ASK_CARBON_PROVIDER_TIMEOUT_MS",
];

export class PublicApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = "PublicApiError";
    this.status = status;
    this.code = code;
  }
}

export const splitCsv = (value) =>
  String(value ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

export const parsePositiveInteger = (value) => {
  if (!/^[1-9]\d*$/.test(String(value ?? ""))) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
};

export const parsePositiveNumber = (value) => {
  if (!/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(String(value ?? ""))) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

export const activationStatus = (env, knowledge, now = new Date()) => {
  const reasons = [];
  if (env.ASK_CARBON_ACTIVATION !== "enabled") reasons.push("activation_disabled");
  for (const key of ACTIVATION_REQUIREMENTS) {
    if (!env[key]) reasons.push(`missing_${key.toLowerCase()}`);
  }
  if (!env.ASK_CARBON_USAGE_LEDGER?.idFromName || !env.ASK_CARBON_USAGE_LEDGER?.get) {
    reasons.push("missing_usage_ledger_binding");
  }
  if (knowledge.release_status !== "APPROVED_PUBLIC") reasons.push("knowledge_not_approved");
  if (!knowledge.source_release_date) reasons.push("missing_source_release_date");
  if (!knowledge.expires_at) {
    reasons.push("missing_knowledge_expiry");
  } else if (!Number.isFinite(Date.parse(knowledge.expires_at)) || Date.parse(knowledge.expires_at) <= now.getTime()) {
    reasons.push("knowledge_expired_or_invalid");
  }
  const approvedModels = splitCsv(env.ASK_CARBON_APPROVED_MODELS);
  if (env.ASK_CARBON_MODEL && !approvedModels.includes(env.ASK_CARBON_MODEL)) reasons.push("model_not_approved");
  if (!splitCsv(env.ASK_CARBON_APPROVED_ORIGINS).length) reasons.push("no_approved_origins");
  if (!parsePositiveNumber(env.ASK_CARBON_INPUT_USD_PER_MILLION)) reasons.push("invalid_input_price");
  if (!parsePositiveNumber(env.ASK_CARBON_OUTPUT_USD_PER_MILLION)) reasons.push("invalid_output_price");
  if (!parsePositiveInteger(env.ASK_CARBON_DAILY_REQUEST_LIMIT)) reasons.push("invalid_request_limit");
  if (!parsePositiveInteger(env.ASK_CARBON_DAILY_COST_MICRO_USD_LIMIT)) reasons.push("invalid_cost_limit");
  if (!parsePositiveInteger(env.ASK_CARBON_MAX_CONCURRENCY)) reasons.push("invalid_concurrency_limit");
  if (!parsePositiveInteger(env.ASK_CARBON_CLIENT_REQUESTS_PER_HOUR)) reasons.push("invalid_client_rate_limit");
  if (!parsePositiveInteger(env.ASK_CARBON_MAX_INPUT_TOKENS)) reasons.push("invalid_max_input_tokens");
  if (!parsePositiveInteger(env.ASK_CARBON_MAX_OUTPUT_TOKENS)) reasons.push("invalid_max_output_tokens");
  if (!parsePositiveInteger(env.ASK_CARBON_PROVIDER_TIMEOUT_MS)) reasons.push("invalid_provider_timeout");
  const sourceIds = new Set((knowledge.sources ?? []).map((source) => source.id));
  if (!Array.isArray(knowledge.sources) || sourceIds.size !== knowledge.sources.length) reasons.push("invalid_source_manifest");
  if (!Array.isArray(knowledge.cards) || !knowledge.cards.length) reasons.push("empty_knowledge_cards");
  if ((knowledge.cards ?? []).some((card) => !Array.isArray(card.source_ids) || !card.source_ids.length || card.source_ids.some((id) => !sourceIds.has(id)))) {
    reasons.push("unknown_card_source");
  }
  if ((knowledge.sources ?? []).some((source) => !["ALREADY_PUBLIC", "PUBLIC_REPOSITORY", "APPROVED_PUBLIC"].includes(source.release_status))) {
    reasons.push("source_not_publicly_releasable");
  }
  return {
    active: reasons.length === 0,
    reasons: [...new Set(reasons)].sort(),
    knowledge_version: knowledge.knowledge_version,
    source_release_date: knowledge.source_release_date,
    expires_at: knowledge.expires_at,
  };
};

export const normalizeOrigin = (value) => {
  try {
    const url = new URL(value);
    if (!/^https?:$/.test(url.protocol) || url.username || url.password || url.pathname !== "/" || url.search || url.hash) return null;
    return url.origin;
  } catch {
    return null;
  }
};

export const assertAllowedOrigin = (request, env) => {
  const requestOrigin = normalizeOrigin(request.headers.get("origin"));
  const allowed = splitCsv(env.ASK_CARBON_APPROVED_ORIGINS).map(normalizeOrigin).filter(Boolean);
  if (!requestOrigin || !allowed.includes(requestOrigin)) {
    throw new PublicApiError(403, "origin_not_allowed", "This request origin is not allowed.");
  }
  return requestOrigin;
};

export const corsHeaders = (origin) => ({
  "access-control-allow-origin": origin,
  "access-control-allow-methods": "POST, OPTIONS",
  "access-control-allow-headers": "content-type",
  "access-control-max-age": "600",
  vary: "Origin",
});

const assertPlainObject = (value, message) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new PublicApiError(400, "invalid_request", message);
  }
};

export const validateRequestBody = (value) => {
  assertPlainObject(value, "The request body must be an object.");
  const allowedKeys = new Set(["question", "turns"]);
  if (Object.keys(value).some((key) => !allowedKeys.has(key))) {
    throw new PublicApiError(400, "invalid_request", "The request contains unsupported fields.");
  }
  if (typeof value.question !== "string") {
    throw new PublicApiError(400, "invalid_question", "A question is required.");
  }
  const question = value.question.trim();
  if (!question || question.length > MAX_QUESTION_LENGTH) {
    throw new PublicApiError(400, "invalid_question", `Questions must contain 1 to ${MAX_QUESTION_LENGTH} characters.`);
  }
  if (/(?:api[_ -]?key|private[_ -]?key|password|secret)\s*[:=]\s*\S+/i.test(question)) {
    throw new PublicApiError(400, "possible_secret", "Please remove credentials or secrets before asking a public question.");
  }
  const turns = value.turns ?? [];
  if (!Array.isArray(turns) || turns.length > MAX_CONTEXT_TURNS) {
    throw new PublicApiError(400, "invalid_context", `At most ${MAX_CONTEXT_TURNS} prior turns are accepted.`);
  }
  const normalizedTurns = turns.map((turn) => {
    assertPlainObject(turn, "Each prior turn must be an object.");
    if (Object.keys(turn).some((key) => !["question", "answer"].includes(key))) {
      throw new PublicApiError(400, "invalid_context", "A prior turn contains unsupported fields.");
    }
    if (typeof turn.question !== "string" || typeof turn.answer !== "string") {
      throw new PublicApiError(400, "invalid_context", "Prior turns require question and answer text.");
    }
    if (!turn.question.trim() || !turn.answer.trim() || turn.question.length > MAX_TURN_TEXT_LENGTH || turn.answer.length > MAX_TURN_TEXT_LENGTH) {
      throw new PublicApiError(400, "invalid_context", "A prior turn is empty or too long.");
    }
    return { question: turn.question.trim(), answer: turn.answer.trim() };
  });
  return { question, turns: normalizedTurns };
};

export const selectCards = (knowledge, question, limit = 6) => {
  const tokens = new Set(question.toLowerCase().match(/[a-z0-9]+/g) ?? []);
  return knowledge.cards
    .filter((card) => card.id !== "unknown-answer")
    .map((card) => {
      const terms = [...(card.keywords ?? []), ...card.question.toLowerCase().match(/[a-z0-9]+/g) ?? []];
      const score = terms.reduce((total, term) => total + (tokens.has(term.toLowerCase()) ? 1 : 0), 0);
      return { card, score };
    })
    .sort((left, right) => right.score - left.score || left.card.id.localeCompare(right.card.id))
    .slice(0, limit)
    .map(({ card }) => card);
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

const hmacKey = (secret) => crypto.subtle.importKey(
  "raw",
  encoder.encode(secret),
  { name: "HMAC", hash: "SHA-256" },
  false,
  ["sign", "verify"],
);

export const signBoundedContext = async (payload, secret) => {
  const encoded = base64UrlEncode(encoder.encode(JSON.stringify(payload)));
  const key = await hmacKey(secret);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(encoded));
  return `${encoded}.${base64UrlEncode(new Uint8Array(signature))}`;
};

export const verifyBoundedContext = async (token, secret, nowSeconds = Math.floor(Date.now() / 1000)) => {
  if (typeof token !== "string" || token.split(".").length !== 2) throw new PublicApiError(500, "invalid_context_signature", "Bounded context verification failed.");
  const [encoded, signature] = token.split(".");
  const key = await hmacKey(secret);
  const valid = await crypto.subtle.verify("HMAC", key, base64UrlDecode(signature), encoder.encode(encoded));
  if (!valid) throw new PublicApiError(500, "invalid_context_signature", "Bounded context verification failed.");
  const payload = JSON.parse(decoder.decode(base64UrlDecode(encoded)));
  if (!Number.isSafeInteger(payload.iat) || !Number.isSafeInteger(payload.exp) || payload.exp <= nowSeconds || payload.iat > nowSeconds + 5) {
    throw new PublicApiError(500, "expired_context", "Bounded context is expired or invalid.");
  }
  return payload;
};

export const makeBoundedContext = async ({ question, turns, cards, knowledge, requestId, secret, nowSeconds }) => {
  const payload = {
    v: 1,
    request_id: requestId,
    knowledge_version: knowledge.knowledge_version,
    source_ids: [...new Set(cards.flatMap((card) => card.source_ids))].sort(),
    card_ids: cards.map((card) => card.id),
    question,
    turns,
    iat: nowSeconds,
    exp: nowSeconds + CONTEXT_TTL_SECONDS,
  };
  return { payload, token: await signBoundedContext(payload, secret) };
};

export const answerSchema = {
  type: "object",
  additionalProperties: false,
  required: ["answer", "source_ids", "follow_ups", "maturity_note"],
  properties: {
    answer: { type: "string", minLength: 1, maxLength: 1400 },
    source_ids: { type: "array", minItems: 1, maxItems: 4, uniqueItems: true, items: { type: "string" } },
    follow_ups: { type: "array", maxItems: 3, items: { type: "string", minLength: 1, maxLength: 160 } },
    maturity_note: { type: ["string", "null"], maxLength: 300 },
  },
};

export const validateProviderOutput = (value, allowedSourceIds) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned an invalid result.");
  const keys = Object.keys(value);
  if (keys.some((key) => !["answer", "source_ids", "follow_ups", "maturity_note"].includes(key)) || keys.length !== 4) {
    throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned unsupported fields.");
  }
  if (typeof value.answer !== "string" || !value.answer.trim() || value.answer.length > 1400) throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned invalid answer text.");
  if (!Array.isArray(value.source_ids) || value.source_ids.length < 1 || value.source_ids.length > 4 || new Set(value.source_ids).size !== value.source_ids.length) {
    throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned invalid source references.");
  }
  if (value.source_ids.some((id) => typeof id !== "string" || !allowedSourceIds.has(id))) {
    throw new PublicApiError(502, "unknown_source", "The answer provider referenced an unapproved source.");
  }
  if (!Array.isArray(value.follow_ups) || value.follow_ups.length > 3 || value.follow_ups.some((item) => typeof item !== "string" || !item.trim() || item.length > 160)) {
    throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned invalid follow-up questions.");
  }
  if (value.maturity_note !== null && (typeof value.maturity_note !== "string" || value.maturity_note.length > 300)) {
    throw new PublicApiError(502, "invalid_provider_output", "The answer provider returned an invalid maturity note.");
  }
  return {
    answer: value.answer.trim(),
    source_ids: value.source_ids,
    follow_ups: value.follow_ups.map((item) => item.trim()),
    maturity_note: value.maturity_note?.trim() || null,
  };
};

export const extractResponseText = (body) => {
  if (typeof body?.output_text === "string" && body.output_text) return body.output_text;
  const fragments = [];
  for (const item of body?.output ?? []) {
    if (item?.type !== "message" || item?.role !== "assistant") continue;
    for (const content of item.content ?? []) {
      if (content?.type === "output_text" && typeof content.text === "string") fragments.push(content.text);
    }
  }
  return fragments.join("");
};

export const calculateCostMicroUsd = ({ inputTokens, outputTokens, inputUsdPerMillion, outputUsdPerMillion }) => {
  const inputCost = inputTokens * inputUsdPerMillion;
  const outputCost = outputTokens * outputUsdPerMillion;
  return Math.ceil(inputCost + outputCost);
};

export const estimateMaxCostMicroUsd = (env) => calculateCostMicroUsd({
  inputTokens: parsePositiveInteger(env.ASK_CARBON_MAX_INPUT_TOKENS),
  outputTokens: parsePositiveInteger(env.ASK_CARBON_MAX_OUTPUT_TOKENS),
  inputUsdPerMillion: parsePositiveNumber(env.ASK_CARBON_INPUT_USD_PER_MILLION),
  outputUsdPerMillion: parsePositiveNumber(env.ASK_CARBON_OUTPUT_USD_PER_MILLION),
});

export const sha256Hex = async (value) => {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
};

export const publicSources = (knowledge, sourceIds) => sourceIds.map((id) => {
  const source = knowledge.sources.find((candidate) => candidate.id === id);
  if (!source) throw new PublicApiError(502, "unknown_source", "An approved source could not be resolved.");
  return { id: source.id, title: source.title, url: source.url, note: source.note };
});
