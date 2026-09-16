const MAX_QUESTION_LENGTH = 1200;
const MAX_CONTEXT_TURNS = 4;
const DEFAULT_KNOWLEDGE_URL = "/ask-carbon/public-knowledge.v1.json";
const DEFAULT_API_URL = "/api/ask-carbon";

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
  const normalized = question.toLowerCase();
  if (card.question.toLowerCase() === normalized.trim()) return 1000;
  const words = new Set(normalized.match(/[a-z0-9]+/g) ?? []);
  const keywordScore = (card.keywords ?? []).reduce(
    (score, keyword) => score + (words.has(keyword.toLowerCase()) ? 2 : normalized.includes(keyword.toLowerCase()) ? 1 : 0),
    0,
  );
  const questionScore = (card.question.toLowerCase().match(/[a-z0-9]+/g) ?? []).reduce(
    (score, word) => score + (words.has(word) ? 1 : 0),
    0,
  );
  return keywordScore + questionScore;
};

export const findSavedAnswer = (knowledge, question) => {
  if (/\b(ignore|override|disregard)\b.{0,80}\b(instruction|source|rule|say|claim)/i.test(question)) {
    return knowledge.cards.find((card) => card.id === "unknown-answer");
  }
  const ranked = knowledge.cards
    .map((card) => ({ card, score: scoreCard(card, question) }))
    .sort((left, right) => right.score - left.score || left.card.id.localeCompare(right.card.id));
  return ranked[0]?.score > 0 ? ranked[0].card : knowledge.cards.find((card) => card.id === "unknown-answer");
};

export const createThreadGuard = () => {
  let generation = 0;
  let controller = null;
  return {
    begin() {
      controller?.abort();
      controller = new AbortController();
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
    this.liveStatus = { active: false };
    this.turns = [];
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
    const date = this.liveStatus.source_release_date || this.knowledge?.source_release_date || this.knowledge?.sources?.[0]?.observed_at || "date unavailable";
    if (this.liveStatus.active) {
      this.status.textContent = `Live answers · Reviewed public sources dated ${date}.`;
      this.mode.textContent = "Live public answer";
      this.privacy.textContent = "Questions are sent to the approved AI provider. Do not paste confidential engineering or customer data.";
      return;
    }
    this.status.textContent = `Interactive preview · Saved explanations, not live AI. Draft sources observed ${date}.`;
    this.mode.textContent = "Saved explanation";
    this.privacy.textContent = "This preview uses saved public explanations. It sends no questions to an AI provider. Do not paste confidential data.";
  }

  renderIntro() {
    if (!this.main) return;
    this.main.replaceChildren();
    const doc = this.ownerDocument;
    const intro = createElement(doc, "section", { className: "ask-carbon-intro" });
    intro.append(
      createElement(doc, "h3", { text: "Understand how Carbon works." }),
      createElement(doc, "p", { text: "Start with a question. Ask for more detail as you go." }),
    );
    const topics = createElement(doc, "div", { className: "ask-carbon-topics" });
    const starterIds = ["how-carbon-works", "training-cases", "reference-answers", "progress-maturity"];
    for (const id of starterIds) {
      const card = this.knowledge?.cards?.find((item) => item.id === id);
      const fallback = {
        "how-carbon-works": ["The basics", "How does Carbon work?"],
        "training-cases": ["Training", "Who chooses the training cases?"],
        "reference-answers": ["Verification", "Where does the ground truth come from?"],
        "progress-maturity": ["Progress", "What has been proven?"],
      }[id];
      const button = createElement(doc, "button", {
        className: "ask-carbon-topic",
        attributes: { type: "button", "data-card-id": id },
      });
      button.append(
        createElement(doc, "span", { className: "ask-carbon-topic-label", text: card?.topic ?? fallback[0] }),
        createElement(doc, "span", { className: "ask-carbon-topic-question", text: card?.question ?? fallback[1] }),
      );
      button.disabled = !card;
      button.addEventListener("click", () => this.ask(card.question));
      topics.append(button);
    }
    intro.append(
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
    article.append(createElement(doc, "p", { className: "ask-carbon-answer-text", text: answer.answer }));
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
        if (source.note) item.append(` — ${source.note}`);
        list.append(item);
      }
      details.append(list);
      article.append(details);
    }
    if (answer.follow_ups?.length) {
      const followups = createElement(doc, "div", { className: "ask-carbon-followups" });
      for (const question of answer.follow_ups.slice(0, 3)) {
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
    return (card.source_ids ?? []).map((id) => this.knowledge.sources.find((source) => source.id === id)).filter(Boolean);
  }

  async ask(rawQuestion) {
    const question = rawQuestion.trim();
    if (!question || question.length > MAX_QUESTION_LENGTH || !this.knowledge) return;
    const thread = this.main.querySelector(".ask-carbon-thread") ?? this.renderThread();
    this.addUserMessage(thread, question);
    this.input.value = "";
    this.counter.textContent = `0 / ${MAX_QUESTION_LENGTH.toLocaleString()}`;
    this.setBusy(true);
    this.status.textContent = this.liveStatus.active ? "Finding a supported answer from approved public sources…" : "Finding the closest saved public explanation…";
    const request = this.guard.begin();
    try {
      let answer;
      if (this.liveStatus.active) {
        answer = await this.askLive(question, request.signal);
      } else {
        const card = findSavedAnswer(this.knowledge, question);
        answer = { ...card, sources: this.sourcesFor(card) };
        await Promise.resolve();
      }
      if (!request.isCurrent()) return;
      this.turns.push({ question, answer: answer.answer });
      this.turns = this.turns.slice(-MAX_CONTEXT_TURNS);
      this.addAnswer(thread, answer);
    } catch (error) {
      if (error.name !== "AbortError" && request.isCurrent()) this.renderError(error.message);
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
      body: JSON.stringify({ question, turns: this.turns.slice(-MAX_CONTEXT_TURNS) }),
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
  }

  reset() {
    this.guard.reset();
    this.turns = [];
    this.setBusy(false);
    this.renderIntro();
    this.input.value = "";
    this.counter.textContent = `0 / ${MAX_QUESTION_LENGTH.toLocaleString()}`;
    this.status.textContent = "New chat started. " + (this.liveStatus.active ? "Live public answers are available." : "Saved explanations are ready.");
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
      "button:not([disabled]), textarea:not([disabled]), a[href], details > summary",
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
