import { evaluateRelease } from "./release-contract.js";

const MAX_QUESTION_LENGTH = 1200;
const DEFAULT_KNOWLEDGE_URL = "/ask-carbon/public-knowledge.v1.json";
const DEFAULT_API_URL = "/api/ask-carbon";
const DEFAULT_PILOT_URL = "/ask-carbon/pilot-designer.html";
const RETRIEVAL_STOP_WORDS = new Set(["a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "how", "i", "in", "is", "it", "of", "on", "or", "that", "the", "their", "this", "to", "was", "what", "when", "where", "which", "who", "why", "with", "you"]);

const retrievalTokens = (value) => (String(value ?? "").toLowerCase().match(/[a-z0-9]+/g) ?? [])
  .filter((word) => word.length > 1 && !RETRIEVAL_STOP_WORDS.has(word));

export const shouldUseLiveAnswers = (liveStatus, visitorEnabled) => liveStatus?.active === true && visitorEnabled === true;

const createElement = (documentRef, tag, options = {}) => {
  const element = documentRef.createElement(tag);
  if (options.className) element.className = options.className;
  if (options.text !== undefined) element.textContent = options.text;
  for (const [name, value] of Object.entries(options.attributes ?? {})) {
    element.setAttribute(name, value);
  }
  return element;
};

const scoreCard = (card, question) => {
  const normalized = question.trim().toLowerCase();
  const cardQuestions = card.questions ?? [card.question].filter(Boolean);
  if (cardQuestions.some((item) => item.toLowerCase() === normalized)) return 1000;
  const queryTerms = new Set(retrievalTokens(normalized));
  const cardTerms = new Set(retrievalTokens(`${cardQuestions.join(" ")} ${(card.keywords ?? []).join(" ")}`));
  if (![...queryTerms].some((term) => cardTerms.has(term))) return 0;
  const words = new Set(normalized.match(/[a-z0-9]+/g) ?? []);
  const keywordScore = (card.keywords ?? []).reduce(
    (score, keyword) => score + (words.has(keyword.toLowerCase()) ? 2 : normalized.includes(keyword.toLowerCase()) ? 1 : 0),
    0,
  );
  const questionScore = (cardQuestions.join(" ").toLowerCase().match(/[a-z0-9]+/g) ?? []).reduce(
    (score, word) => score + (words.has(word) ? 1 : 0),
    0,
  );
  return keywordScore + questionScore;
};

export const findSavedAnswer = (knowledge, question, { eligibleCardIds = null, priorCardIds = [] } = {}) => {
  if (/\b(ignore|override|disregard)\b.{0,80}\b(instruction|source|rule|say|claim)/i.test(question)) {
    return null;
  }
  const eligible = eligibleCardIds ? new Set(eligibleCardIds) : null;
  const needsContext = /\b(those|they|them|their|it|that|this|these)\b/i.test(question) || (question.match(/[a-z0-9]+/gi) ?? []).length <= 3;
  const prior = new Set(needsContext ? priorCardIds : []);
  const ranked = knowledge.cards
    .filter((card) => !eligible || eligible.has(card.id))
    .map((card) => ({ card, score: scoreCard(card, question) + (prior.has(card.id) ? 3 : 0) + (card.related ?? []).filter((id) => prior.has(id)).length * 2 }))
    .sort((left, right) => right.score - left.score || left.card.id.localeCompare(right.card.id));
  return ranked[0]?.score >= 2 ? ranked[0].card : null;
};

export const createThreadGuard = () => {
  let generation = 0;
  let controller = null;
  return {
    begin() {
      controller?.abort();
      controller = new AbortController();
      generation += 1;
      const requestGeneration = generation;
      return { signal: controller.signal, isCurrent: () => requestGeneration === generation };
    },
    reset() {
      generation += 1;
      controller?.abort();
      controller = null;
    },
  };
};

const HTMLElementBase = globalThis.HTMLElement ?? class {};

export class AskCarbonElement extends HTMLElementBase {
  constructor() {
    super();
    this.knowledge = null;
    this.releaseStatus = null;
    this.liveStatus = { active: false };
    this.liveEnabled = false;
    this.continuation = null;
    this.savedCardIds = [];
    this.guard = createThreadGuard();
    this.lastFocused = null;
    this.onKeydown = this.onKeydown.bind(this);
  }

  connectedCallback() {
    if (this.dataset.ready === "true") return;
    this.dataset.ready = "true";
    this.renderShell();
    this.loadState();
    if (new URL(globalThis.location.href).searchParams.get("ask-carbon") === "open") this.open();
  }

  renderShell() {
    const doc = this.ownerDocument;
    this.launcher = createElement(doc, "button", {
      className: "ask-carbon-launcher",
      text: "Ask Carbon",
      attributes: { type: "button", "aria-haspopup": "dialog", "aria-expanded": "false" },
    });
    this.backdrop = createElement(doc, "div", { className: "ask-carbon-backdrop" });
    this.backdrop.hidden = true;
    this.dialog = createElement(doc, "section", {
      className: "ask-carbon-dialog",
      attributes: { role: "dialog", "aria-modal": "true", "aria-labelledby": "ask-carbon-title" },
    });

    const header = createElement(doc, "header", { className: "ask-carbon-header" });
    const brand = createElement(doc, "div", { className: "ask-carbon-brand" });
    brand.append(
      createElement(doc, "p", { className: "ask-carbon-eyebrow", text: "Physics AI for engineers" }),
      createElement(doc, "h2", { text: "Ask Carbon", attributes: { id: "ask-carbon-title" } }),
    );
    const actions = createElement(doc, "div", { className: "ask-carbon-actions" });
    this.resetButton = createElement(doc, "button", {
      className: "ask-carbon-utility",
      text: "New chat",
      attributes: { type: "button" },
    });
    this.closeButton = createElement(doc, "button", {
      className: "ask-carbon-close",
      text: "×",
      attributes: { type: "button", "aria-label": "Close Ask Carbon" },
    });
    actions.append(this.resetButton, this.closeButton);
    header.append(brand, actions);

    this.status = createElement(doc, "div", {
      className: "ask-carbon-status",
      text: "Loading reviewed public sources…",
      attributes: { role: "status", "aria-live": "polite" },
    });
    this.main = createElement(doc, "div", { className: "ask-carbon-main" });
    this.renderIntro();

    const composer = createElement(doc, "form", { className: "ask-carbon-composer" });
    const meta = createElement(doc, "div", { className: "ask-carbon-composer-meta" });
    const modeWrap = createElement(doc, "span", { text: "Answer depth " });
    this.mode = createElement(doc, "span", { className: "ask-carbon-mode", text: "Saved explanation" });
    modeWrap.append(this.mode);
    this.counter = createElement(doc, "span", { text: `0 / ${MAX_QUESTION_LENGTH.toLocaleString()}` });
    meta.append(modeWrap, this.counter);
    const inputRow = createElement(doc, "div", { className: "ask-carbon-input-row" });
    this.input = createElement(doc, "textarea", {
      className: "ask-carbon-input",
      attributes: {
        maxlength: String(MAX_QUESTION_LENGTH),
        rows: "2",
        placeholder: "Ask how Carbon works…",
        "aria-label": "Question about how Carbon works",
      },
    });
    this.submitButton = createElement(doc, "button", {
      className: "ask-carbon-submit",
      text: "→",
      attributes: { type: "submit", "aria-label": "Ask question" },
    });
    inputRow.append(this.input, this.submitButton);
    this.input.disabled = true;
    this.submitButton.disabled = true;
    this.privacy = createElement(doc, "p", {
      className: "ask-carbon-privacy",
      text: "Saved explanations run on this page. Do not paste confidential engineering or customer data.",
    });
    composer.append(meta, inputRow, this.privacy);

    this.dialog.append(header, this.status, this.main, composer);
    this.backdrop.append(this.dialog);
    this.append(this.launcher, this.backdrop);

    this.launcher.addEventListener("click", () => this.open());
    this.closeButton.addEventListener("click", () => this.close());
    this.resetButton.addEventListener("click", () => this.reset());
    this.backdrop.addEventListener("click", (event) => {
      if (event.target === this.backdrop) this.close();
    });
    this.input.addEventListener("input", () => {
      this.counter.textContent = `${this.input.value.length.toLocaleString()} / ${MAX_QUESTION_LENGTH.toLocaleString()}`;
    });
    this.input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        composer.requestSubmit();
      }
    });
    composer.addEventListener("submit", (event) => {
      event.preventDefault();
      this.ask(this.input.value);
    });
  }

  async loadState() {
    const knowledgeUrl = this.getAttribute("knowledge-url") || DEFAULT_KNOWLEDGE_URL;
    const apiUrl = this.getAttribute("api-url") || DEFAULT_API_URL;
    try {
      const [knowledgeResponse, healthResponse] = await Promise.all([
        fetch(knowledgeUrl, { credentials: "same-origin", cache: "no-store" }),
        fetch(`${apiUrl}/health`, { credentials: "same-origin", cache: "no-store" }).catch(() => null),
      ]);
      if (!knowledgeResponse.ok) throw new Error("Public explanations are unavailable.");
      this.knowledge = await knowledgeResponse.json();
      if (healthResponse?.ok) this.liveStatus = await healthResponse.json();
      const mode = this.hasAttribute("staging-preview") ? "staging" : "production";
      this.releaseStatus = evaluateRelease(this.knowledge, { mode });
      if (!this.releaseStatus.valid && !this.liveStatus.active) throw new Error("No approved, current public explanation release is available.");
      this.updateStatus();
      this.renderIntro();
      this.setBusy(false);
    } catch (error) {
      this.status.textContent = "Public explanations are temporarily unavailable.";
      this.renderError(error.message);
      this.input.disabled = true;
      this.submitButton.disabled = true;
    }
  }

  updateStatus() {
    const date = this.liveStatus.source_release_date || this.knowledge?.release?.source_release_date || "date unavailable";
    if (shouldUseLiveAnswers(this.liveStatus, this.liveEnabled)) {
      this.status.textContent = `Live answers · Reviewed public sources dated ${date}.`;
      this.mode.textContent = "Live public answer";
      this.privacy.textContent = "Questions are sent to the approved AI provider. Do not paste confidential engineering or customer data.";
      return;
    }
    const staging = this.hasAttribute("staging-preview");
    this.status.textContent = this.liveStatus.active
      ? "Saved explanations ready · Live AI stays off until you review the data use and enable it."
      : staging
        ? `Private staging preview · Reviewed saved explanations, not live AI. Sources released ${date}.`
        : `Saved public explanations · Sources released ${date}.`;
    this.mode.textContent = staging ? "Staging explanation" : "Saved explanation";
    this.privacy.textContent = "Saved explanations run in this page and send no question to an AI provider. Do not paste confidential data.";
  }

  renderIntro() {
    if (!this.main) return;
    this.main.replaceChildren();
    const doc = this.ownerDocument;
    const intro = createElement(doc, "section", { className: "ask-carbon-intro" });
    intro.append(
      createElement(doc, "h3", { text: "Understand how Carbon works." }),
      createElement(doc, "p", { text: "Choose whether to learn about Carbon or draft a high-level pilot brief." }),
    );
    const pathways = createElement(doc, "div", { className: "ask-carbon-pathways", attributes: { "aria-label": "Choose an Ask Carbon path" } });
    const learn = createElement(doc, "button", { className: "ask-carbon-pathway", attributes: { type: "button" } });
    learn.append(
      createElement(doc, "span", { className: "ask-carbon-pathway-title", text: "Learn about Carbon" }),
      createElement(doc, "span", { className: "ask-carbon-pathway-note", text: "Ask a public question and inspect the reviewed sources." }),
    );
    const pilot = createElement(doc, "a", {
      className: "ask-carbon-pathway",
      attributes: { href: this.getAttribute("pilot-url") || DEFAULT_PILOT_URL },
    });
    pilot.append(
      createElement(doc, "span", { className: "ask-carbon-pathway-title", text: "Draft a pilot" }),
      createElement(doc, "span", { className: "ask-carbon-pathway-note", text: "Use the local form, or affirmatively enable bounded AI guidance." }),
    );
    pathways.append(learn, pilot);
    if (this.liveStatus.active && !this.liveEnabled) {
      const disclosure = createElement(doc, "section", {
        className: "ask-carbon-live-disclosure",
        attributes: { "aria-labelledby": "ask-carbon-live-title" },
      });
      disclosure.append(
        createElement(doc, "h4", { text: "Before enabling live AI answers", attributes: { id: "ask-carbon-live-title" } }),
        createElement(doc, "p", { text: "Saved explanations send nothing to the AI provider. If enabled, your current question and bounded reviewed public passages are sent through Carbon’s server to the OpenAI API. Contact details are not requested or sent." }),
        createElement(doc, "p", { text: "Requests use store:false, but Carbon has not established Zero Data Retention or Modified Abuse Monitoring. Prompts and responses may be retained by the provider for up to 30 days. Do not include confidential, personal, credential, solver, model, customer or protected-evaluation information." }),
      );
      const consentLabel = createElement(doc, "label", { className: "ask-carbon-consent" });
      const consent = createElement(doc, "input", { attributes: { type: "checkbox" } });
      consentLabel.append(consent, " I understand and want to enable live AI answers.");
      const enable = createElement(doc, "button", {
        className: "ask-carbon-enable-live",
        text: "Enable live answers",
        attributes: { type: "button", disabled: "" },
      });
      consent.addEventListener("change", () => { enable.disabled = !consent.checked; });
      enable.addEventListener("click", () => {
        if (!consent.checked) return;
        this.liveEnabled = true;
        this.updateStatus();
        this.renderIntro();
        this.input.focus();
      });
      disclosure.append(consentLabel, enable);
      intro.append(disclosure);
    }
    const topics = createElement(doc, "div", { className: "ask-carbon-topics" });
    const starterIds = ["overview", "training-control", "references", "current-progress"];
    for (const id of starterIds) {
      const card = this.knowledge?.cards?.find((item) => item.id === id);
      const fallback = {
        "overview": ["The basics", "How does Carbon work?"],
        "training-control": ["Training", "Who chooses the training cases?"],
        "references": ["Verification", "Where does the ground truth come from?"],
        "current-progress": ["Progress", "What has been proven?"],
      }[id];
      const button = createElement(doc, "button", {
        className: "ask-carbon-topic",
        attributes: { type: "button", "data-card-id": id },
      });
      button.append(
        createElement(doc, "span", { className: "ask-carbon-topic-label", text: card?.topic ?? fallback[0] }),
        createElement(doc, "span", { className: "ask-carbon-topic-question", text: card?.questions?.[0] ?? fallback[1] }),
      );
      button.disabled = !card;
      button.addEventListener("click", () => this.ask(card.questions[0]));
      topics.append(button);
    }
    learn.addEventListener("click", () => topics.querySelector("button:not([disabled])")?.focus());
    intro.append(
      pathways,
      createElement(doc, "p", { className: "ask-carbon-section-label", text: "Start with a public question" }),
      topics,
      createElement(doc, "p", {
        className: "ask-carbon-hint",
        text: "You can ask about Challenge design, miner recipes, independent testing, evidence limits, qualification and current progress.",
      }),
    );
    this.main.append(intro);
  }

  renderThread() {
    const thread = createElement(this.ownerDocument, "div", {
      className: "ask-carbon-thread",
      attributes: { "aria-live": "polite" },
    });
    this.main.replaceChildren(thread);
    return thread;
  }

  addUserMessage(thread, text) {
    thread.append(createElement(this.ownerDocument, "p", { className: "ask-carbon-message ask-carbon-message--user", text }));
  }

  addAnswer(thread, answer) {
    const doc = this.ownerDocument;
    const article = createElement(doc, "article", { className: "ask-carbon-message ask-carbon-message--answer" });
    if (answer.mode_label) article.append(createElement(doc, "p", { className: "ask-carbon-answer-mode", text: answer.mode_label }));
    article.append(createElement(doc, "p", { className: "ask-carbon-answer-text", text: answer.answer }));
    if (answer.maturity_note) article.append(createElement(doc, "p", { className: "ask-carbon-maturity", text: answer.maturity_note }));
    const sources = (answer.sources ?? []).filter((source) => source?.url && source?.title);
    if (sources.length) {
      const details = createElement(doc, "details", { className: "ask-carbon-source-details" });
      details.append(createElement(doc, "summary", { text: `Inspect ${sources.length === 1 ? "source" : "sources"}` }));
      const list = createElement(doc, "ul", { className: "ask-carbon-source-list" });
      for (const source of sources) {
        const item = createElement(doc, "li");
        const link = createElement(doc, "a", {
          text: source.title,
          attributes: { href: source.url, target: "_blank", rel: "noopener noreferrer" },
        });
        item.append(link);
        const metadata = [source.sections?.join(", "), source.revision ? `revision ${source.revision.slice(0, 12)}` : null, source.note].filter(Boolean).join(" · ");
        if (metadata) item.append(` — ${metadata}`);
        list.append(item);
      }
      details.append(list);
      article.append(details);
    }
    const questions = answer.follow_up ? [answer.follow_up] : (answer.follow_ups ?? []).slice(0, 1);
    if (questions.length) {
      const followups = createElement(doc, "div", { className: "ask-carbon-followups" });
      for (const question of questions) {
        const button = createElement(doc, "button", { className: "ask-carbon-followup", text: question, attributes: { type: "button" } });
        button.addEventListener("click", () => this.ask(question));
        followups.append(button);
      }
      article.append(followups);
    }
    thread.append(article);
    article.scrollIntoView({ block: "nearest" });
  }

  renderError(message) {
    const target = this.main.querySelector(".ask-carbon-thread") ?? this.renderThread();
    target.append(createElement(this.ownerDocument, "p", {
      className: "ask-carbon-error",
      text: message || "Ask Carbon could not answer that question. Please try again.",
      attributes: { role: "alert" },
    }));
  }

  sourcesFor(card) {
    const sourceIds = [...new Set((card.passages ?? []).map((passage) => passage.source_id))];
    return sourceIds.map((id) => this.knowledge.sources.find((source) => source.id === id)).filter(Boolean);
  }

  async ask(rawQuestion) {
    const question = rawQuestion.trim();
    if (!question || question.length > MAX_QUESTION_LENGTH || !this.knowledge) return;
    const thread = this.main.querySelector(".ask-carbon-thread") ?? this.renderThread();
    this.addUserMessage(thread, question);
    this.input.value = "";
    this.counter.textContent = `0 / ${MAX_QUESTION_LENGTH.toLocaleString()}`;
    this.setBusy(true);
    this.status.textContent = shouldUseLiveAnswers(this.liveStatus, this.liveEnabled) ? "Finding a supported answer from approved public sources…" : "Finding the closest saved public explanation…";
    const request = this.guard.begin();
    try {
      let answer;
      if (shouldUseLiveAnswers(this.liveStatus, this.liveEnabled)) {
        answer = await this.askLive(question, request.signal);
      } else {
        const card = findSavedAnswer(this.knowledge, question, { eligibleCardIds: this.releaseStatus?.eligible_card_ids, priorCardIds: this.savedCardIds });
        answer = card ? {
          status: "saved_explanation",
          answer: card.answer,
          follow_up: card.questions?.[1] ?? null,
          maturity_note: `${card.maturity}: ${card.scope_note}`,
          mode_label: this.hasAttribute("staging-preview") ? "Reviewed staging explanation — not live AI" : "Approved saved explanation — not live AI",
          sources: this.sourcesFor(card),
          card_id: card.id,
        } : {
          status: "insufficient_evidence",
          answer: "I don't have a relevant reviewed explanation for that question. Try naming the Carbon mechanism or project area you mean.",
          follow_up: "Which part of Carbon would you like explained?",
          sources: [],
          mode_label: "No relevant saved evidence",
        };
        await Promise.resolve();
      }
      if (!request.isCurrent()) return;
      this.continuation = answer.continuation ?? this.continuation;
      if (answer.card_id) this.savedCardIds = [answer.card_id, ...this.savedCardIds.filter((id) => id !== answer.card_id)].slice(0, 4);
      this.addAnswer(thread, answer);
    } catch (error) {
      if (error.name !== "AbortError" && request.isCurrent()) {
        const fallback = findSavedAnswer(this.knowledge, question, { eligibleCardIds: this.releaseStatus?.eligible_card_ids, priorCardIds: this.savedCardIds });
        if (shouldUseLiveAnswers(this.liveStatus, this.liveEnabled) && fallback && this.releaseStatus?.valid) {
          this.addAnswer(thread, {
            status: "saved_explanation",
            answer: fallback.answer,
            follow_up: null,
            maturity_note: `${fallback.maturity}: ${fallback.scope_note}`,
            mode_label: "Live answer unavailable — showing an approved saved explanation",
            sources: this.sourcesFor(fallback),
            card_id: fallback.id,
          });
        } else this.renderError(error.message);
      }
    } finally {
      if (request.isCurrent()) {
        this.setBusy(false);
        this.updateStatus();
      }
    }
  }

  async askLive(question, signal) {
    const apiUrl = this.getAttribute("api-url") || DEFAULT_API_URL;
    const response = await fetch(apiUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, ...(this.continuation ? { continuation: this.continuation } : {}) }),
      signal,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error?.message || "Ask Carbon is temporarily unavailable.");
    return body;
  }

  setBusy(busy) {
    const disabled = busy || !this.knowledge;
    this.input.disabled = disabled;
    this.submitButton.disabled = disabled;
    this.submitButton.textContent = busy ? "…" : "→";
    for (const button of this.main?.querySelectorAll?.(".ask-carbon-topic, .ask-carbon-followup") ?? []) button.disabled = busy;
  }

  reset() {
    this.guard.reset();
    this.continuation = null;
    this.savedCardIds = [];
    this.setBusy(false);
    this.renderIntro();
    this.input.value = "";
    this.counter.textContent = `0 / ${MAX_QUESTION_LENGTH.toLocaleString()}`;
    this.status.textContent = "New chat started. " + (shouldUseLiveAnswers(this.liveStatus, this.liveEnabled) ? "Live public answers remain enabled for this page." : "Saved explanations are ready.");
    this.input.focus();
  }

  open() {
    if (!this.backdrop.hidden) return;
    this.lastFocused = this.ownerDocument.activeElement;
    this.backdrop.hidden = false;
    this.launcher.setAttribute("aria-expanded", "true");
    this.ownerDocument.body.classList.add("ask-carbon-open");
    this.ownerDocument.addEventListener("keydown", this.onKeydown);
    queueMicrotask(() => this.closeButton.focus());
  }

  close() {
    if (this.backdrop.hidden) return;
    this.backdrop.hidden = true;
    this.launcher.setAttribute("aria-expanded", "false");
    this.ownerDocument.body.classList.remove("ask-carbon-open");
    this.ownerDocument.removeEventListener("keydown", this.onKeydown);
    this.lastFocused?.focus?.();
  }

  onKeydown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      this.close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...this.dialog.querySelectorAll(
      "button:not([disabled]), textarea:not([disabled]), input:not([disabled]), a[href], details > summary",
    )].filter((node) => node.getClientRects().length > 0);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && this.ownerDocument.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && this.ownerDocument.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}

if (globalThis.customElements && !customElements.get("ask-carbon")) {
  customElements.define("ask-carbon", AskCarbonElement);
}
