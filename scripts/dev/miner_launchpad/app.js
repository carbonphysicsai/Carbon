"use strict";
(() => {
  let token = "";
  let selected = "";
  let runs = [];
  let pending = null;
  let busy = false;
  let polling = false;
  const $ = id => document.getElementById(id);
  const message = (text, error = false) => {
    $("message").textContent = text;
    $("message").className = error ? "message error" : "message";
  };
  async function api(path, body, key) {
    const headers = {Authorization: "Bearer " + token};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (key) headers["Idempotency-Key"] = key;
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST", headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(5000), cache: "no-store", redirect: "error"
    });
    const result = await response.json();
    if (!response.ok) {
      const error = new Error(result.error || "request_failed");
      error.status = response.status;
      throw error;
    }
    return result;
  }
  function render() {
    const picker = $("run-picker");
    picker.replaceChildren();
    for (const run of runs) {
      const option = document.createElement("option");
      option.value = run.id;
      option.textContent = run.id.slice(0, 10) + " · " + run.state;
      picker.append(option);
    }
    const run = runs.find(r => r.id === selected) || runs[0];
    $("empty").hidden = Boolean(run);
    $("run-detail").hidden = !run;
    picker.hidden = !run;
    $("picker-label").hidden = !run;
    if (!run) return;
    selected = run.id;
    picker.value = selected;
    $("run-id").textContent = run.id;
    $("run-state").textContent = run.state;
    $("run-steps").textContent = run.steps + " / " + run.spec.max_steps;
    $("progress").max = run.spec.max_steps;
    $("progress").value = run.steps;
    $("deadline").textContent = "Fixed deadline: " + new Date(run.deadline * 1000).toLocaleString();
    $("pause").disabled = busy || !["QUEUED", "RUNNING"].includes(run.state);
    $("resume").disabled = busy || !["PAUSED", "INTERRUPTED"].includes(run.state);
    $("stop").disabled = busy || !["QUEUED", "RUNNING", "PAUSED", "INTERRUPTED"].includes(run.state);
    const events = $("events");
    events.replaceChildren();
    for (const event of run.events.slice(-30).reverse()) {
      const item = document.createElement("li");
      const at = document.createElement("time");
      at.textContent = new Date(event.at * 1000).toLocaleTimeString();
      const kind = document.createElement("span");
      kind.textContent = event.kind.replaceAll("_", " ");
      item.append(at, kind);
      events.append(item);
    }
  }
  async function refresh() {
    if (!token || polling) return;
    polling = true;
    try {
      runs = (await api("/api/v1/runs")).runs;
      render();
      $("connection-state").textContent = "Connected";
    } catch (error) {
      $("connection-state").textContent = "Connection interrupted";
      message("Controller connection interrupted. Runs may still be active. Reconnect before issuing another command.", true);
    } finally { polling = false; }
  }
  $("connect-form").addEventListener("submit", async event => {
    event.preventDefault();
    token = $("token").value.trim();
    try {
      const catalog = await api("/api/v1/capabilities");
      if (catalog.schema !== "carbon.launchpad.rehearsal.v1" || catalog.mode !== "REHEARSAL") {
        throw new Error("unsupported_controller_version");
      }
      $("token").value = "";
      $("launch-fields").disabled = false;
      $("integrations").replaceChildren();
      for (const item of catalog.unavailable) {
        const card = document.createElement("div"); card.className = "integration";
        const title = document.createElement("strong"); title.textContent = item.id;
        const reason = document.createElement("p"); reason.textContent = item.reason.replaceAll("_", " ");
        card.append(title, reason); $("integrations").append(card);
      }
      message("Connected. Rehearsal records persist on this machine. No external provider is enabled.");
      await refresh();
    } catch (error) {
      token = "";
      $("launch-fields").disabled = true;
      message("Could not connect: " + error.message, true);
    }
  });
  $("launch-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy) return;
    if (!pending) {
      pending = {key: crypto.randomUUID(), spec: {
        mode: "REHEARSAL", challenge: "controller-rehearsal-v1", agent: "fixture",
        reasoning: "none", compute: "local", max_steps: Number($("steps").value),
        max_seconds: Number($("seconds").value)
      }};
    }
    busy = true; $("launch-button").disabled = true;
    try {
      const run = await api("/api/v1/runs", pending.spec, pending.key);
      selected = run.id; pending = null;
      message("Rehearsal started. These fixture steps produce no physics or mining evidence.");
      $("launch-button").firstChild.textContent = "Launch rehearsal ";
      await refresh();
    } catch (error) {
      if (error.status >= 400 && error.status < 500 && error.message !== "idempotency_key_conflict") {
        pending = null;
        message("Launch rejected: " + error.message + ". Correct the request or free an active slot before retrying.", true);
      } else {
        message("Launch not confirmed: " + error.message + ". Retry reuses the same request and cannot create a second run.", true);
        $("launch-button").firstChild.textContent = "Retry same launch ";
      }
    } finally { busy = false; $("launch-button").disabled = false; render(); }
  });
  for (const action of ["pause", "resume", "stop"]) {
    $(action).addEventListener("click", async () => {
      if (busy || !selected) return;
      busy = true; render();
      try {
        await api("/api/v1/runs/" + selected + "/" + action, {});
        message("Controller acknowledged: " + action + ".");
        await refresh();
      } catch (error) { message("Command not confirmed: " + error.message + ". Check the run state before retrying.", true); }
      finally { busy = false; render(); }
    });
  }
  $("run-picker").addEventListener("change", () => { selected = $("run-picker").value; render(); });
  $("export").addEventListener("click", () => {
    const run = runs.find(r => r.id === selected);
    if (!run) return;
    const blob = new Blob([JSON.stringify(run, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url;
    anchor.download = "carbon-rehearsal-" + run.id + ".json";
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  setInterval(refresh, 1500);
})();
