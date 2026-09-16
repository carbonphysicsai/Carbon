import { PublicApiError } from "./errors.mjs";

export const PRICING_OBSERVED_AT = "2026-09-16";
export const MODEL_PROFILES = Object.freeze({
  "gpt-5.6-luna:low:v1": Object.freeze({
    config_id: "gpt-5.6-luna:low:v1",
    request_model: "gpt-5.6-luna",
    allowed_response_models: Object.freeze(["gpt-5.6-luna"]),
    pricing_id: "openai-standard-2026-09-16:gpt-5.6-luna",
    input_price_micro_usd_per_million: 200_000,
    cached_input_price_micro_usd_per_million: 20_000,
    output_price_micro_usd_per_million: 1_200_000,
    reasoning_effort: "low",
    verbosity: "low",
    supports_strict_json_schema: true,
    requires_reasoning_usage: true,
    context_window_tokens: 1_050_000,
    model_max_output_tokens: 128_000,
    framing_token_allowance: 512,
    pricing_source: "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
  }),
  "gpt-5.6-terra:low:v1": Object.freeze({
    config_id: "gpt-5.6-terra:low:v1",
    request_model: "gpt-5.6-terra",
    allowed_response_models: Object.freeze(["gpt-5.6-terra"]),
    pricing_id: "openai-standard-2026-09-16:gpt-5.6-terra",
    input_price_micro_usd_per_million: 2_000_000,
    cached_input_price_micro_usd_per_million: 200_000,
    output_price_micro_usd_per_million: 12_000_000,
    reasoning_effort: "low",
    verbosity: "low",
    supports_strict_json_schema: true,
    requires_reasoning_usage: true,
    context_window_tokens: 1_050_000,
    model_max_output_tokens: 128_000,
    framing_token_allowance: 512,
    pricing_source: "https://developers.openai.com/api/docs/models/gpt-5.6-terra",
  }),
});

export const getModelProfile = (configId) => MODEL_PROFILES[configId] ?? null;

const ceilRatio = (numerator, denominator) => (numerator + denominator - 1n) / denominator;
const costPart = (tokens, price) => BigInt(tokens) * BigInt(price);

export const calculateUsageCostMicroUsd = (profile, usage) => {
  const uncached = usage.input_tokens - usage.cached_input_tokens;
  const numerator = costPart(uncached, profile.input_price_micro_usd_per_million) +
    costPart(usage.cached_input_tokens, profile.cached_input_price_micro_usd_per_million) +
    costPart(usage.output_tokens, profile.output_price_micro_usd_per_million);
  const result = ceilRatio(numerator, 1_000_000n);
  if (result > BigInt(Number.MAX_SAFE_INTEGER)) throw new PublicApiError(500, "unsupported_accounting", "The provider cost cannot be represented safely.");
  return Number(result);
};

export const estimateMaximumCostMicroUsd = (profile, { maxInputTokens, maxOutputTokens }) => {
  if (!Number.isSafeInteger(maxInputTokens) || maxInputTokens <= 0 || maxInputTokens > profile.context_window_tokens ||
      !Number.isSafeInteger(maxOutputTokens) || maxOutputTokens <= 0 || maxOutputTokens > profile.model_max_output_tokens) {
    throw new PublicApiError(500, "unsupported_accounting", "The configured token bounds are unsupported.");
  }
  const numerator = costPart(maxInputTokens, profile.input_price_micro_usd_per_million) +
    costPart(maxOutputTokens, profile.output_price_micro_usd_per_million);
  const result = ceilRatio(numerator, 1_000_000n);
  if (result > BigInt(Number.MAX_SAFE_INTEGER)) throw new PublicApiError(500, "unsupported_accounting", "The provider reservation cannot be represented safely.");
  return Number(result);
};

export const validateProviderUsage = (body, profile) => {
  const usage = body?.usage;
  const values = [usage?.input_tokens, usage?.output_tokens, usage?.total_tokens];
  if (!values.every((value) => Number.isSafeInteger(value) && value >= 0) ||
      usage.total_tokens !== usage.input_tokens + usage.output_tokens) {
    throw new PublicApiError(502, "untrusted_provider_usage", "The answer provider returned incomplete or invalid usage accounting.");
  }
  const cached = usage.input_tokens_details?.cached_tokens ?? 0;
  if (!Number.isSafeInteger(cached) || cached < 0 || cached > usage.input_tokens) {
    throw new PublicApiError(502, "untrusted_provider_usage", "The answer provider returned invalid cached-token accounting.");
  }
  const reasoning = usage.output_tokens_details?.reasoning_tokens;
  if (profile.requires_reasoning_usage && (!Number.isSafeInteger(reasoning) || reasoning < 0 || reasoning > usage.output_tokens)) {
    throw new PublicApiError(502, "untrusted_provider_usage", "The answer provider returned incomplete reasoning-token accounting.");
  }
  return {
    input_tokens: usage.input_tokens,
    cached_input_tokens: cached,
    output_tokens: usage.output_tokens,
    reasoning_tokens: reasoning ?? 0,
    total_tokens: usage.total_tokens,
  };
};

export const assertProviderModel = (body, profile) => {
  if (!profile.allowed_response_models.includes(body?.model)) {
    throw new PublicApiError(502, "provider_model_mismatch", "The answer provider returned an unexpected model identity.");
  }
  return body.model;
};
