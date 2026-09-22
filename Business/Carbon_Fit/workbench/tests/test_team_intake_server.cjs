"use strict";
// Real HTTP against the real private receiver, its real durable store and its
// real role checks. Nothing here is a public receiver, a delivered notification
// or a live customer submission.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { DurableIntakeStore } = require("../tools/team_intake_store.cjs");
const { createIntakeServer, loadUsers } = require("../tools/team_intake_server.cjs");
const ROOT = path.resolve(__dirname, "..");
const I = require("../src/intake.js");

const TOKENS = {
  receiver: "receiver-token-0000000000000000",
  reviewer: "reviewer-token-0000000000000000",
  steward: "steward-token-0000000000000000",
  notifier: "notifier-token-0000000000000000",
  stranger: "stranger-token-0000000000000000",
};
const digest = (value) => crypto.createHash("sha256").update(value).digest("hex");

const TEAM = "carbon-fit", OTHER_TEAM = "other-tenant";
// Synthetic accounts. A directory holds credential digests and never a
// credential; the tokens above exist only inside this test process.
const account = (principal, roles, token, team = TEAM) => ({
  principal,
  team,
  roles,
  token_sha256: digest(token),
  status: "ACTIVE",
});
const USERS = [
  account("receiver-account", ["INTAKE_RECEIVER"], TOKENS.receiver),
  account("reviewer-account", ["TEAM_REVIEWER"], TOKENS.reviewer),
  account("steward-account", ["DATA_STEWARD"], TOKENS.steward),
  account("operations-account", ["NOTIFICATION_OPERATOR"], TOKENS.notifier),
  // Every role this receiver defines, and none of this team's records. The
  // denial below is about who owns the inquiry, not about what the caller may
  // do, which is the case a role check alone would let through.
  account(
    "foreign-account",
    ["INTAKE_RECEIVER", "TEAM_REVIEWER", "DATA_STEWARD", "NOTIFICATION_OPERATOR"],
    TOKENS.stranger,
    OTHER_TEAM,
  ),
];

function reviewedRaw(distinct = false) {
  const brief = JSON.parse(
    fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"),
  );
  if (distinct) brief.draft_id = "synthetic-second-draft";
  return JSON.stringify({
    schema_version: I.REVIEW_VERSION,
    brief,
    pilot: {
      label: "Draft pilot for Carbon review",
      ...Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, ""])),
      bounded_first_pilot: "Compare the reported baseline over an agreed synthetic range.",
    },
    field_provenance: [
      ...I.TEXT_FIELDS,
      ...I.QUANTITY_FIELDS,
      ...I.PILOT_FIELDS.map((field) => "pilot." + field),
    ].map((field) => ({
      field,
      origin: field === "pilot.bounded_first_pilot" ? "CLIENT_TYPED" : "UNKNOWN",
      suggestion_id: null,
    })),
    accepted_suggestions: [],
    unresolved_assumptions: ["Reference adequacy is unknown."],
    ai_guidance: {
      enabled: false,
      provider: null,
      guidance_version: I.GUIDANCE_VERSION,
      notice_version: null,
      consented_at: null,
      cleared_locally: false,
    },
    sharing: { include_conversation: false, conversation: [] },
    contact: { name: "", email: "", organization: "" },
    local_scope: I.REVIEW_SCOPE,
  });
}

async function started() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-intake-server-"));
  const usersFile = path.join(directory, "users.json");
  fs.writeFileSync(usersFile, JSON.stringify(USERS));
  const store = new DurableIntakeStore(path.join(directory, "store.json"), {
    destination: "Hello@carbonphysics.ai",
  });
  const server = createIntakeServer({ store, users: loadUsers(usersFile) });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const call = (method, route, { token, body, headers } = {}) =>
    fetch(base + route, {
      method,
      headers: {
        ...(token ? { authorization: "Bearer " + token } : {}),
        ...(body ? { "content-type": "application/json" } : {}),
        ...headers,
      },
      body,
    });
  return { directory, store, server, call, close: () => server.close() };
}

test("one inquiry and one notification intent survive a lost response and a restart", async () => {
  const fixture = await started();
  try {
    const raw = reviewedRaw();
    const first = await fixture.call("POST", "/private/intake", {
      token: TOKENS.receiver,
      body: raw,
      headers: { "idempotency-key": "submit-001" },
    });
    assert.equal(first.status, 201);
    const receipt = await first.json();
    assert.equal(receipt.disposition, "ACCEPTED");
    assert.equal(receipt.status, "PERSISTED_PRIVATE_SYNTHETIC");

    // The client never saw the first response and retried the same bytes.
    const retry = await fixture.call("POST", "/private/intake", {
      token: TOKENS.receiver,
      body: raw,
      headers: { "idempotency-key": "submit-001" },
    });
    const retried = await retry.json();
    assert.equal(retried.disposition, "DEDUPLICATED");
    assert.equal(retried.inquiry_id, receipt.inquiry_id);

    // The same key with different bytes is a conflict, not a second record.
    const conflict = await fixture.call("POST", "/private/intake", {
      token: TOKENS.receiver,
      body: raw + " ",
      headers: { "idempotency-key": "submit-001" },
    });
    assert.equal(conflict.status, 409);

    const reopened = new DurableIntakeStore(fixture.store.filePath);
    assert.equal(Object.keys(reopened.state.inquiries).length, 1);
    assert.equal(Object.keys(reopened.state.outbox).length, 1);
  } finally {
    fixture.close();
  }
});

test("every endpoint checks the caller's role and denies an unrelated principal", async () => {
  const fixture = await started();
  try {
    const accepted = await (
      await fixture.call("POST", "/private/intake", {
        token: TOKENS.receiver,
        body: reviewedRaw(),
        headers: { "idempotency-key": "submit-002" },
      })
    ).json();
    const id = accepted.inquiry_id;
    const denied = [
      ["POST", "/private/intake", TOKENS.reviewer],
      ["GET", `/private/intake/${id}/export`, TOKENS.receiver],
      ["PATCH", `/private/intake/${id}`, TOKENS.receiver],
      ["DELETE", `/private/intake/${id}`, TOKENS.reviewer],
      ["GET", "/private/outbox", TOKENS.reviewer],
      [
        "POST",
        `/private/outbox/notify-${id}/attempt`,
        TOKENS.reviewer,
      ],
    ];
    for (const [method, route, token] of denied) {
      const result = await fixture.call(method, route, {
        token,
        body: method === "POST" || method === "PATCH" ? "{}" : undefined,
      });
      assert.equal(result.status, 403, `${method} ${route}`);
    }
    // No credential at all is refused before anything is read.
    assert.equal((await fixture.call("GET", `/private/intake/${id}`)).status, 403);
    assert.equal(
      (await fixture.call("GET", `/private/intake/${id}`, { token: "not-a-known-token-000000" })).status,
      403,
    );
    // A fully-roled principal from another team is refused, and refused as a
    // 404: whether this receiver holds that inquiry is not something a foreign
    // caller gets to learn by watching the status code change.
    const foreign = await fixture.call("GET", `/private/intake/${id}`, {
      token: TOKENS.stranger,
    });
    assert.equal(foreign.status, 404);
    assert.equal(
      (await fixture.call("GET", "/private/intake/inquiry-000000000000000", {
        token: TOKENS.stranger,
      })).status,
      404,
    );
    for (const route of [`/private/intake/${id}/export`, "/private/outbox"])
      assert.equal(
        [404, 200].includes((await fixture.call("GET", route, { token: TOKENS.stranger })).status),
        true,
      );
    // ... and its view of the queue is empty rather than another team's.
    assert.deepEqual(
      (await (await fixture.call("GET", "/private/outbox", { token: TOKENS.stranger })).json()).events,
      [],
    );

    // The allowed roles still work.
    assert.equal(
      (await fixture.call("GET", `/private/intake/${id}`, { token: TOKENS.reviewer })).status,
      200,
    );
    assert.equal(
      (await fixture.call("GET", `/private/intake/${id}/export`, { token: TOKENS.reviewer })).status,
      200,
    );
  } finally {
    fixture.close();
  }
});

test("a triage revision is append-only over HTTP and a stale version conflicts", async () => {
  const fixture = await started();
  try {
    const accepted = await (
      await fixture.call("POST", "/private/intake", {
        token: TOKENS.receiver,
        body: reviewedRaw(),
        headers: { "idempotency-key": "submit-003" },
      })
    ).json();
    const id = accepted.inquiry_id;
    const patch = (version, note, queue_state) =>
      fixture.call("PATCH", `/private/intake/${id}`, {
        token: TOKENS.reviewer,
        headers: { "if-match": String(version) },
        body: JSON.stringify({ assigned_reviewer: "Nick", note, queue_state }),
      });
    const first = await (await patch(1, "First reading.", "UNDER_REVIEW")).json();
    assert.equal(first.version, 2);
    const second = await (await patch(2, "Corrected.", "READY_FOR_ROUTE")).json();
    assert.equal(second.version, 3);
    assert.equal(
      second.assessments.at(-1).superseded_team_fields.note,
      "First reading.",
    );
    assert.equal((await patch(2, "stale", "PARKED")).status, 409);
    const current = await (
      await fixture.call("GET", `/private/intake/${id}`, { token: TOKENS.reviewer })
    ).json();
    assert.equal(current.team_fields.note, "Corrected.");
    assert.equal(current.assessments.length, 2);
  } finally {
    fixture.close();
  }
});

test("the outbox is observable and a failed attempt is never reported as delivery", async () => {
  const fixture = await started();
  try {
    const accepted = await (
      await fixture.call("POST", "/private/intake", {
        token: TOKENS.receiver,
        body: reviewedRaw(),
        headers: { "idempotency-key": "submit-004" },
      })
    ).json();
    const listed = await (
      await fixture.call("GET", "/private/outbox", { token: TOKENS.notifier })
    ).json();
    assert.equal(listed.events.length, 1);
    assert.equal(listed.events[0].destination, "Hello@carbonphysics.ai");
    assert.equal(listed.events[0].status, "PENDING");
    assert.equal(
      listed.events[0].notification.record_path,
      "/private/intake/" + accepted.inquiry_id,
    );
    // No client words leave the receiver in the notification projection.
    assert.equal(
      JSON.stringify(listed.events[0]).includes("Compare the reported baseline"),
      false,
    );

    const attempt = await fixture.call(
      "POST",
      `/private/outbox/notify-${accepted.inquiry_id}/attempt`,
      { token: TOKENS.notifier },
    );
    // No transport exists at all: the route always calls the store without a
    // handler. 502 would say a gateway was reached and misbehaved, sending an
    // operator after a network fault that does not exist. 501 says this server
    // cannot perform the delivery, which is the true state.
    assert.equal(attempt.status, 501);
    const attempted = await attempt.json();
    assert.equal(attempted.last_outcome, "NOT_ATTEMPTED_NO_TRANSPORT");
    assert.equal(attempted.status, "PENDING");
    assert.equal(attempted.attempts, 0, "an attempt was counted for a delivery nobody tried");
    assert.equal(attempted.last_error, "");
    // The inquiry is untouched by any of this.
    assert.equal(
      (await fixture.call("GET", `/private/intake/${accepted.inquiry_id}`, { token: TOKENS.reviewer })).status,
      200,
    );
  } finally {
    fixture.close();
  }
});

test("hostile request bodies and unknown routes reject without storing anything", async () => {
  const fixture = await started();
  try {
    const hostile = [
      ["not json at all", "submit-005"],
      [JSON.stringify({ schema_version: "carbon.client-intake.draft.v1" }), "submit-006"],
      [reviewedRaw(), "../../escape"],
      ["x".repeat(140_000), "submit-007"],
    ];
    for (const [body, key] of hostile) {
      const result = await fixture.call("POST", "/private/intake", {
        token: TOKENS.receiver,
        body,
        headers: { "idempotency-key": key },
      });
      assert.equal(result.status >= 400, true, key);
    }
    assert.equal(
      (await fixture.call("GET", "/private/unknown", { token: TOKENS.reviewer })).status,
      404,
    );
    assert.equal(
      (await fixture.call("GET", "/private/intake/inquiry-absent", { token: TOKENS.reviewer })).status,
      404,
    );
    const reopened = new DurableIntakeStore(fixture.store.filePath);
    assert.deepEqual(Object.keys(reopened.state.inquiries), []);
  } finally {
    fixture.close();
  }
});

test("the retention lifecycle is reachable over HTTP and each step checks its own role", async () => {
  const fixture = await started();
  try {
    const accepted = await (
      await fixture.call("POST", "/private/intake", {
        token: TOKENS.receiver,
        body: reviewedRaw(),
        headers: { "idempotency-key": "submit-retention-001" },
      })
    ).json();
    const id = accepted.inquiry_id;

    // Deletion without an approved exception is refused, and the refusal is
    // about retention rather than about the caller's role.
    const premature = await fixture.call("DELETE", `/private/intake/${id}`, {
      token: TOKENS.steward,
    });
    assert.equal(premature.status, 400);
    assert.match((await premature.json()).error, /approved retention exception/);

    // Every retention route refuses a caller without the steward role.
    for (const [method, route, body] of [
      ["POST", `/private/intake/${id}/archive`, "{}"],
      ["POST", `/private/intake/${id}/restore`, "{}"],
      ["POST", `/private/intake/${id}/deletion-exception`, JSON.stringify({ approver: "Ryan Bequette", reason: "Synthetic cleanup." })],
    ])
      assert.equal(
        (await fixture.call(method, route, { token: TOKENS.reviewer, body })).status,
        403,
        `${method} ${route}`,
      );

    const archived = await fixture.call("POST", `/private/intake/${id}/archive`, {
      token: TOKENS.steward, body: "{}",
    });
    assert.equal(archived.status, 200);
    assert.equal((await archived.json()).lifecycle, "ARCHIVED");

    // Out of the working set, and an export of it has to be asked for.
    assert.deepEqual(
      (await (await fixture.call("GET", "/private/intake", { token: TOKENS.reviewer })).json()).inquiries,
      [],
    );
    assert.equal(
      (await (await fixture.call("GET", "/private/intake?archived=include", { token: TOKENS.reviewer })).json()).inquiries.length,
      1,
    );
    assert.equal(
      (await fixture.call("GET", `/private/intake/${id}/export`, { token: TOKENS.reviewer })).status,
      400,
    );
    assert.equal(
      (await fixture.call("GET", `/private/intake/${id}/export?archived=include`, { token: TOKENS.reviewer })).status,
      200,
    );

    const exception = await fixture.call("POST", `/private/intake/${id}/deletion-exception`, {
      token: TOKENS.steward,
      body: JSON.stringify({ approver: "Ryan Bequette", reason: "Synthetic fixture cleanup only." }),
    });
    assert.equal(exception.status, 201);
    assert.equal((await exception.json()).approver, "Ryan Bequette");
    // An approval with no named approver is refused rather than attributed to
    // the authenticated caller: who approved a deletion and who carried it out
    // are different facts, and conflating them is how an approval disappears.
    assert.equal(
      (await fixture.call("POST", `/private/intake/${id}/deletion-exception`, {
        token: TOKENS.steward, body: JSON.stringify({ reason: "Synthetic cleanup." }),
      })).status,
      400,
    );

    const deleted = await fixture.call("DELETE", `/private/intake/${id}`, { token: TOKENS.steward });
    assert.equal(deleted.status, 200);
    const tombstone = await deleted.json();
    assert.equal(tombstone.approved_by, "Ryan Bequette");
    assert.equal(tombstone.deleted_by, "steward-account");
    assert.deepEqual(tombstone.did_not_reach, ["RETAINED_ARCHIVE", "PRIOR_EXPORTS", "PROVIDER_RECORDS"]);
    assert.equal(
      (await fixture.call("GET", `/private/intake/${id}`, { token: TOKENS.reviewer })).status,
      404,
    );
  } finally {
    fixture.close();
  }
});

test("the receiver holds no state of its own and mints no identity", () => {
  // The role checks live in the store, and this is what makes "every endpoint
  // is checked" true for routes as well: a route has nothing to read except
  // through a store method that validates its principal. A route that reached
  // into `store.state` would bypass every one of them, and a route that built
  // its own principal would bypass authentication, so neither may appear here.
  const source = fs.readFileSync(path.join(ROOT, "tools/team_intake_server.cjs"), "utf8");
  assert.equal(/store\.state/.test(source), false);
  assert.equal(/new StaffPrincipal|ISSUED_BY_AUTHENTICATION/.test(source), false);
  // Exactly one place resolves an identity, and it is the directory.
  assert.equal((source.match(/directory\.authenticate/g) || []).length, 1);
  // Falsification: the same reading applied to a source that does reach in.
  const reaching = source.replace("store.search(principal", "store.state.inquiries; store.search(principal");
  assert.equal(/store\.state/.test(reaching), true);
});

test("a store with no room refuses with insufficient storage, not bad request", async () => {
  // A relayed export the store had no room for was not a bad request. Reporting
  // 400 would send the relaying receiver to correct a package that is correct.
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-team-capacity-"));
  const usersFile = path.join(directory, "users.json");
  fs.writeFileSync(usersFile, JSON.stringify(USERS));
  const storePath = path.join(directory, "store.json");
  const roomy = new DurableIntakeStore(storePath);
  const first = await roomy.accept(reviewedRaw(), "capacity-001", loadUsers(usersFile).authenticate("Bearer " + TOKENS.receiver));

  const store = new DurableIntakeStore(storePath, {
    writeCeilingBytes: fs.statSync(storePath).size + 32,
  });
  const server = createIntakeServer({ store, users: loadUsers(usersFile) });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  try {
    const result = await fetch(`http://127.0.0.1:${port}/private/intake`, {
      method: "POST",
      headers: {
        authorization: "Bearer " + TOKENS.receiver,
        "idempotency-key": "capacity-002",
        "content-type": "application/json",
      },
      body: reviewedRaw(true),
    });
    assert.equal(result.status, 507);
    assert.match((await result.json()).error, /byte ceiling/);

    // The capacity route is how an operator sees this coming.
    const capacity = await fetch(`http://127.0.0.1:${port}/private/capacity`, {
      headers: { authorization: "Bearer " + TOKENS.steward },
    });
    assert.equal(capacity.status, 200);
    const report = await capacity.json();
    assert.equal(report.inquiries, 1);
    assert(report.remaining_bytes < 64);
    assert(report.read_limit_bytes > report.ceiling_bytes);
    // Reading capacity is a steward action like the other recovery endpoints.
    assert.equal(
      (await fetch(`http://127.0.0.1:${port}/private/capacity`, {
        headers: { authorization: "Bearer " + TOKENS.reviewer },
      })).status,
      403,
    );

    // And the record that was already accepted is still readable, because the
    // refusal wrote nothing.
    const read = await fetch(`http://127.0.0.1:${port}/private/intake/${first.inquiry_id}`, {
      headers: { authorization: "Bearer " + TOKENS.reviewer },
    });
    assert.equal(read.status, 200);
  } finally {
    server.close();
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
