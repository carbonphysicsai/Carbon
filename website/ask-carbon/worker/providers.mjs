import { PublicApiError } from "./errors.mjs";

// Each provider adapter owns its wire format end to end: the endpoint, the
// secret that authorizes it, the request body, and the normalization of the
// response into one provider-neutral shape. The Worker never reads a raw
// provider body; it reads only what normalize() returns, so a response can
// never be interpreted under the wrong provider's rules.
//
// normalize() returns:
//   { model, usage, completion: "completed" | "incomplete" | "refused", text, response_id }
// and throws a typed PublicApiError for untrusted model identity or usage.

const untrustedUsage = (message) => new PublicApiError(502, "untrusted_provider_usage", message);
const isCount = (value) => Number.isSafeInteger(value) && value >= 0;

export const assertProviderModel = (body, profile) => {
  if (!profile.allowed_response_models.includes(body?.model)) {
    throw new PublicApiError(502, "provider_model_mismatch", "The answer provider returned an unexpected model identity.");
  }
  return body.model;
};

const responsesText = (body) => {
  if (typeof body?.output_text === "string" && body.output_text) return body.output_text;
  const fragments = [];
  for (const item of body?.output ?? []) {
    if (item?.type !== "message" || item?.role !== "assistant") continue;
    for (const content of item.content ?? []) if (content?.type === "output_text" && typeof content.text === "string") fragments.push(content.text);
  }
  return fragments.join("");
};

const openaiResponses = Object.freeze({
  id: "openai_responses",
  url: "https://api.openai.com/v1/responses",
  secret_env: "ASK_CARBON_OPENAI_API_KEY",
  buildBody: (profile, { instructions, userText, schemaName, schema, maxOutputTokens }) => ({
    model: profile.request_model,
    store: false,
    reasoning: { effort: profile.reasoning_effort },
    max_output_tokens: maxOutputTokens,
    instructions,
    input: [{ role: "user", content: [{ type: "input_text", text: userText }] }],
    text: { verbosity: profile.verbosity, format: { type: "json_schema", name: schemaName, strict: true, schema } },
  }),
  normalizeUsage: (body, profile) => {
    const usage = body?.usage;
    if (![usage?.input_tokens, usage?.output_tokens, usage?.total_tokens].every(isCount) ||
        usage.total_tokens !== usage.input_tokens + usage.output_tokens) {
      throw untrustedUsage("The answer provider returned incomplete or invalid usage accounting.");
    }
    const cached = usage.input_tokens_details?.cached_tokens ?? 0;
    if (!isCount(cached) || cached > usage.input_tokens) throw untrustedUsage("The answer provider returned invalid cached-token accounting.");
    const reasoning = usage.output_tokens_details?.reasoning_tokens;
    if (profile.requires_reasoning_usage && (!isCount(reasoning) || reasoning > usage.output_tokens)) {
      throw untrustedUsage("The answer provider returned incomplete reasoning-token accounting.");
    }
    return {
      input_tokens: usage.input_tokens,
      cached_input_tokens: cached,
      output_tokens: usage.output_tokens,
      reasoning_tokens: reasoning ?? 0,
      total_tokens: usage.total_tokens,
    };
  },
  normalizeOutcome: (body) => ({
    completion: body?.status === "completed" ? "completed" : body?.status === "incomplete" ? "incomplete" : "refused",
    text: responsesText(body),
    response_id: typeof body?.id === "string" && body.id ? body.id : null,
  }),
});

// OpenAI-compatible chat/completions, as served by https://llm.chutes.ai/v1.
// Fails closed on anything other than exactly one assistant choice. Output
// tokens are billed from completion_tokens, which already includes any
// reasoning tokens, so reasoning cannot escape the settled cost.
const chutesChatCompletions = Object.freeze({
  id: "chutes_chat_completions",
  url: "https://llm.chutes.ai/v1/chat/completions",
  secret_env: "ASK_CARBON_CHUTES_API_KEY",
  buildBody: (profile, { instructions, userText, schemaName, schema, maxOutputTokens }) => ({
    model: profile.request_model,
    messages: [
      { role: "system", content: instructions },
      { role: "user", content: userText },
    ],
    max_tokens: maxOutputTokens,
    temperature: profile.temperature,
    stream: false,
    response_format: { type: "json_schema", json_schema: { name: schemaName, strict: true, schema } },
  }),
  normalizeUsage: (body) => {
    const usage = body?.usage;
    if (![usage?.prompt_tokens, usage?.completion_tokens, usage?.total_tokens].every(isCount) ||
        usage.total_tokens !== usage.prompt_tokens + usage.completion_tokens) {
      throw untrustedUsage("The answer provider returned incomplete or invalid usage accounting.");
    }
    const cached = usage.prompt_tokens_details?.cached_tokens ?? 0;
    if (!isCount(cached) || cached > usage.prompt_tokens) throw untrustedUsage("The answer provider returned invalid cached-token accounting.");
    const reasoning = usage.completion_tokens_details?.reasoning_tokens ?? 0;
    if (!isCount(reasoning) || reasoning > usage.completion_tokens) throw untrustedUsage("The answer provider returned invalid reasoning-token accounting.");
    return {
      input_tokens: usage.prompt_tokens,
      cached_input_tokens: cached,
      output_tokens: usage.completion_tokens,
      reasoning_tokens: reasoning,
      total_tokens: usage.total_tokens,
    };
  },
  normalizeOutcome: (body) => {
    const choices = Array.isArray(body?.choices) ? body.choices : [];
    const choice = choices.length === 1 ? choices[0] : null;
    const message = choice?.message;
    const content = message?.role === "assistant" && typeof message.content === "string" ? message.content : "";
    const refused = typeof message?.refusal === "string" && message.refusal.length > 0;
    return {
      completion: !choice || refused ? "refused"
        : choice.finish_reason === "stop" ? "completed"
          : choice.finish_reason === "length" ? "incomplete" : "refused",
      text: content,
      response_id: typeof body?.id === "string" && body.id ? body.id : null,
    };
  },
});

export const PROVIDERS = Object.freeze({
  [openaiResponses.id]: openaiResponses,
  [chutesChatCompletions.id]: chutesChatCompletions,
});

export const getProvider = (profile) => PROVIDERS[profile?.provider] ?? null;

// Model identity is checked before usage so a response from an unexpected
// model is never settled at the registered model's prices.
export const normalizeProviderBody = (provider, body, profile) => {
  const model = assertProviderModel(body, profile);
  const usage = provider.normalizeUsage(body, profile);
  return { model, usage };
};
