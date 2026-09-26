"use strict";

// External model processing of a client record: the provider schedule, the
// per-client opt-in, and the one transport.
//
// Three conditions, all required (counsel brief §8.4(c), as the owner relayed
// it on 26 September 2026): the provider is named in the provider schedule; its
// terms carry no training on inputs and zero or minimal retention; and the
// client has separately signed an opt-in. The first two are the schedule. The
// third is per client and defaults off: a record with no opt-in recorded is
// never sent anywhere.
//
// Each is enforced by construction rather than checked by the caller:
//   - a provider can only be built from a schedule entry, so an unscheduled
//     provider or model is not something the store can be handed;
//   - an opt-in can only be issued from a signed-document reference, so a copied
//     literal is refused, in the same way as a record basis (E4);
//   - the transport sends only to the scheduled endpoint.
//
// No transfer is automatic. Nothing in accepting, reading or reviewing a record
// calls a provider; only an explicit, logged `modelAssist` by a reviewer does.
//
// E8 is unrelated and unchanged: nothing here reaches the subnet or the public
// Ask Carbon assistant, and this module imports nothing from either.

const fs = require("node:fs");
const path = require("node:path");

const SCHEDULE_PATH = path.join(__dirname, "..", "data", "client_model_provider_schedule.json");
const SCHEDULE_VERSION = "carbon.private-team-intake.model-provider-schedule.v1";
const REFERENCE = /^[A-Za-z0-9][A-Za-z0-9._:\/-]{2,127}$/;
const CREDENTIAL_MAX_BYTES = 1024;

class ProviderOutcome extends Error {
  constructor(outcome, message, { attempted }) {
    super(message);
    this.outcome = outcome;
    this.attempted = attempted;
  }
}

function loadSchedule(file = SCHEDULE_PATH) {
  const schedule = JSON.parse(fs.readFileSync(file, "utf8"));
  if (schedule.schema_version !== SCHEDULE_VERSION || !Array.isArray(schedule.providers))
    throw Error("Invalid model provider schedule");
  for (const provider of schedule.providers) {
    if (!/^[a-z][a-z0-9-]{1,31}$/.test(provider.id || "")) throw Error("Invalid scheduled provider id");
    const endpoint = new URL(provider.endpoint);
    if (endpoint.protocol !== "https:") throw Error("A scheduled provider is reached over HTTPS only");
    if (!Array.isArray(provider.models) || !provider.models.length) throw Error("A scheduled provider names its models");
  }
  return schedule;
}

// --- The per-client opt-in -------------------------------------------------

const OPT_IN_BRAND = Symbol("carbon.private-team-intake.model-opt-in");
const ISSUED_OPT_INS = new WeakSet();

class ModelOptIn {
  constructor(brand, fields) {
    if (brand !== OPT_IN_BRAND)
      throw Error("A model-processing opt-in can only be issued from the client's signed opt-in");
    Object.assign(this, fields);
    Object.freeze(this);
    ISSUED_OPT_INS.add(this);
  }
}

/**
 * The client's separately signed opt-in, for one scheduled provider. The
 * reference is an opaque identifier for the signed document, held outside the
 * store; no document text is stored.
 */
function signedOptIn({ ref, provider } = {}, schedule = loadSchedule()) {
  if (typeof ref !== "string" || !REFERENCE.test(ref))
    throw Error("A model-processing opt-in names the client's signed opt-in by an opaque reference");
  if (!schedule.providers.some((entry) => entry.id === provider))
    throw Error("A model-processing opt-in names a provider in the provider schedule");
  return new ModelOptIn(OPT_IN_BRAND, { ref, provider });
}

const isModelOptIn = (value) => typeof value === "object" && value !== null && ISSUED_OPT_INS.has(value);

// --- The provider ----------------------------------------------------------

const PROVIDER_BRAND = Symbol("carbon.private-team-intake.scheduled-provider");
const ISSUED_PROVIDERS = new WeakSet();

class ScheduledProvider {
  constructor(brand, fields) {
    if (brand !== PROVIDER_BRAND) throw Error("A model provider can only be built from the provider schedule");
    Object.assign(this, fields);
    Object.freeze(this);
    ISSUED_PROVIDERS.add(this);
  }
}

const isScheduledProvider = (value) => typeof value === "object" && value !== null && ISSUED_PROVIDERS.has(value);

/** The credential, read at send time from its operator file. Never logged. */
function readCredential(file) {
  if (!file)
    throw new ProviderOutcome("NOT_ATTEMPTED_NO_CREDENTIAL", "No model provider credential is configured", { attempted: false });
  let stat;
  try {
    stat = fs.lstatSync(file);
  } catch {
    throw new ProviderOutcome("NOT_ATTEMPTED_NO_CREDENTIAL", "The configured model provider credential file does not exist", { attempted: false });
  }
  if (!stat.isFile() || (stat.mode & 0o077) !== 0 || stat.size > CREDENTIAL_MAX_BYTES)
    throw new ProviderOutcome(
      "NOT_ATTEMPTED_CREDENTIAL_UNSAFE",
      "The model provider credential must be a regular file, not a link, readable by its owner only, and at most 1024 bytes",
      { attempted: false },
    );
  const value = fs.readFileSync(file, "utf8").trim();
  if (!value) throw new ProviderOutcome("NOT_ATTEMPTED_NO_CREDENTIAL", "The configured model provider credential file is empty", { attempted: false });
  return value;
}

/**
 * A provider for one scheduled model. `fetch` is injectable for tests; the
 * endpoint is not, so a test exercises the same URL a live call uses.
 */
function scheduledProvider({ provider, model, credentialFile, fetch = globalThis.fetch, schedule = loadSchedule() } = {}) {
  const entry = schedule.providers.find((candidate) => candidate.id === provider);
  if (!entry) throw Error("The model provider is not in the provider schedule");
  const modelEntry = entry.models.find((candidate) => candidate.id === model);
  if (!modelEntry) throw Error("The model is not in the provider schedule");
  const url = entry.endpoint.replace(/\/$/, "") + "/chat/completions";
  async function complete({ messages, maxTokens }) {
    const credential = readCredential(credentialFile);
    let response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: { authorization: "Bearer " + credential, "content-type": "application/json" },
        body: JSON.stringify({ model, messages, max_tokens: maxTokens, stream: false }),
      });
    } catch {
      // The error text of a failed connection is not carried: it is the
      // platform's, and nothing here decides what it may contain.
      throw new ProviderOutcome("UNREACHABLE", "The model provider could not be reached", { attempted: true });
    }
    // Only the status is kept from a refusal. A provider's error body can echo
    // the request, and the request is client material.
    if (response.status === 401 || response.status === 403)
      throw new ProviderOutcome("CREDENTIAL_REJECTED", `The model provider rejected the credential (${response.status})`, { attempted: true });
    if (!response.ok) throw new ProviderOutcome("PROVIDER_ERROR", `The model provider returned ${response.status}`, { attempted: true });
    let body;
    try {
      body = await response.json();
    } catch {
      throw new ProviderOutcome("PROVIDER_ERROR", "The model provider returned an unreadable response", { attempted: true });
    }
    const message = body && body.choices && body.choices[0] && body.choices[0].message;
    if (!message || typeof message.content !== "string")
      throw new ProviderOutcome("PROVIDER_ERROR", "The model provider returned no message", { attempted: true });
    return {
      content: message.content,
      usage: body.usage
        ? { prompt_tokens: body.usage.prompt_tokens ?? null, completion_tokens: body.usage.completion_tokens ?? null }
        : null,
    };
  }
  return new ScheduledProvider(PROVIDER_BRAND, { id: entry.id, model: modelEntry.id, endpoint: url, complete });
}

/** The provider the operator configured, or null when none is. */
function scheduledProviderFrom(env) {
  const names = ["CARBON_TEAM_MODEL_PROVIDER", "CARBON_TEAM_MODEL", "CARBON_TEAM_MODEL_CREDENTIAL_FILE"];
  if (names.every((name) => !env[name])) return null;
  const missing = names.filter((name) => !env[name]);
  if (missing.length) throw Error("Incomplete model provider configuration: set " + missing.join(", "));
  return scheduledProvider({
    provider: env.CARBON_TEAM_MODEL_PROVIDER,
    model: env.CARBON_TEAM_MODEL,
    credentialFile: env.CARBON_TEAM_MODEL_CREDENTIAL_FILE,
  });
}

module.exports = {
  ModelOptIn,
  ProviderOutcome,
  ScheduledProvider,
  isModelOptIn,
  isScheduledProvider,
  loadSchedule,
  readCredential,
  scheduledProvider,
  scheduledProviderFrom,
  signedOptIn,
};
