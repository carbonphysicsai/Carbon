import { PublicApiError } from "./errors.mjs";
import { assertProviderModel, getProvider } from "./providers.mjs";

export { assertProviderModel };

export const PRICING_OBSERVED_AT = "2026-09-16";
export const MODEL_PROFILES = Object.freeze({
  "gpt-5.6-luna:low:v1": Object.freeze({
    config_id: "gpt-5.6-luna:low:v1",
    provider: "openai_responses",
    production_privacy_mode: "approved_public_privacy_v1",
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
    provider: "openai_responses",
    production_privacy_mode: "approved_public_privacy_v1",
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
  // Prices, context and output limits read from GET https://llm.chutes.ai/v1/models
  // on 2026-09-26 (price.*.usd per million tokens; confidential_compute: true).
  "gemma-4-31b-turbo-tee:v1": Object.freeze({
    config_id: "gemma-4-31b-turbo-tee:v1",
    provider: "chutes_chat_completions",
    // The public notice this provider is disclosed under. Production activation
    // requires the configured privacy mode to equal it, so a provider cannot go
    // live under another provider's notice.
    production_privacy_mode: "approved_public_privacy_v2_chutes_confidential",
    request_model: "google/gemma-4-31B-turbo-TEE",
    allowed_response_models: Object.freeze(["google/gemma-4-31B-turbo-TEE"]),
    pricing_id: "chutes-2026-09-26:google/gemma-4-31B-turbo-TEE",
    input_price_micro_usd_per_million: 120_000,
    cached_input_price_micro_usd_per_million: 12_000,
    output_price_micro_usd_per_million: 370_000,
    reasoning_effort: null,
    verbosity: null,
    temperature: 0,
    supports_strict_json_schema: true,
    requires_reasoning_usage: false,
    confidential_compute: true,
    context_window_tokens: 131_072,
    model_max_output_tokens: 65_536,
    framing_token_allowance: 512,
    pricing_source: "https://llm.chutes.ai/v1/models",
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

export const providerFor = (profile) => {
  const provider = getProvider(profile);
  if (!provider) throw new PublicApiError(500, "unsupported_provider", "The configured answer provider is unsupported.");
  return provider;
};

export const validateProviderUsage = (body, profile) => providerFor(profile).normalizeUsage(body, profile);
