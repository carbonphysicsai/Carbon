"use strict";
(() => {
  let token = "";
  let selected = "";
  let runs = [];
  let pending = null;
  let busy = false;
  let polling = false;
  let connected = false;
  let developmentSources = [];
  const pendingKey = "carbon.launchpad.pending.v1";
  let storageError = false;
  try { pending = JSON.parse(sessionStorage.getItem(pendingKey) || "null"); }
  catch (_) { storageError = true; }
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
    const sources = $("development-sources");
    sources.replaceChildren();
    if (!connected || !developmentSources.length) {
      const note = document.createElement("p"); note.className = "hint";
      note.textContent = connected ? "No DEVELOPMENT source is attached. Real campaign launch is not enabled yet." : "Reconnect to verify current source state.";
      sources.append(note);
    }
    if (connected) for (const source of developmentSources) {
      const card = document.createElement("div"); card.className = "integration";
      const title = document.createElement("h3");
      title.textContent = source.receipt ? source.receipt.disposition : "Readback unavailable";
      const note = document.createElement("p");
      note.textContent = source.receipt ? "DEVELOPMENT EVALUATION · Receipt " + source.receipt.receipt_id : "Source validation failed. No receipt or result is being inferred.";
      const button = document.createElement("button"); button.type = "button";
      button.textContent = "Export verified public receipt";
      button.disabled = busy || source.status !== "VERIFIED_SOURCE";
      button.addEventListener("click", async () => {
        if (busy || !connected) return;
        busy = true; render();
        try {
          const fresh = await api("/api/v1/development/" + source.id);
          if (fresh.status !== "VERIFIED_SOURCE") throw new Error("development_source_unavailable");
          const blob = new Blob([JSON.stringify(fresh, null, 2)], {type: "application/json"});
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement("a"); anchor.href = url;
          anchor.download = "carbon-development-" + source.id + ".json";
          anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (error) { message("Receipt export unavailable: " + error.message, true); }
        finally { busy = false; await refresh(); render(); }
      });
      card.append(title, note, button); sources.append(card);
    }
    $("launch-fields").disabled = !connected || storageError;
    $("launch-button").disabled = busy;
    $("launch-button").firstChild.textContent = pending ? "Retry same launch " : "Launch rehearsal ";
    $("steps").disabled = Boolean(pending);
    $("seconds").disabled = Boolean(pending);
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
    $("pause").disabled = !connected || busy || !["QUEUED", "RUNNING"].includes(run.state);
    $("resume").disabled = !connected || busy || !["PAUSED", "INTERRUPTED"].includes(run.state);
    $("stop").disabled = !connected || busy || !["QUEUED", "RUNNING", "PAUSED", "INTERRUPTED"].includes(run.state);
    $("export").disabled = !connected || busy;
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
      developmentSources = (await api("/api/v1/development")).sources;
      connected = true;
      render();
      $("connection-state").textContent = "Connected";
    } catch (error) {
      connected = false;
      render();
      $("connection-state").textContent = "Connection interrupted";
      message("Controller connection interrupted. Runs may still be active. Reconnect before issuing another command.", true);
    } finally { polling = false; }
  }
  $("connect-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || polling) return;
    connected = false;
    render();
    token = $("token").value.trim();
    try {
      const catalog = await api("/api/v1/capabilities");
      if (catalog.schema !== "carbon.launchpad.rehearsal.v1" || catalog.mode !== "REHEARSAL") {
        throw new Error("unsupported_controller_version");
      }
      $("token").value = "";
      $("integrations").replaceChildren();
      for (const item of catalog.unavailable) {
        const card = document.createElement("div"); card.className = "integration";
        const title = document.createElement("strong"); title.textContent = item.id;
        const reason = document.createElement("p"); reason.textContent = item.reason.replaceAll("_", " ");
        card.append(title, reason); $("integrations").append(card);
      }
      message("Connected. Rehearsal records persist on this machine. No external provider is enabled.");
      await refresh();
      if (storageError) message("Browser retry storage is unavailable. Launch is disabled to preserve duplicate protection.", true);
    } catch (error) {
      token = "";
      connected = false;
      $("connection-state").textContent = "Disconnected";
      render();
      message("Could not connect: " + error.message, true);
    }
  });
  $("launch-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || !connected || storageError) return;
    if (!pending) {
      pending = {key: crypto.randomUUID(), spec: {
        mode: "REHEARSAL", challenge: "controller-rehearsal-v1", agent: "fixture",
        reasoning: "none", compute: "local", max_steps: Number($("steps").value),
        max_seconds: Number($("seconds").value)
      }};
      try { sessionStorage.setItem(pendingKey, JSON.stringify(pending)); }
      catch (_) {
        storageError = true; render();
        message("Could not preserve the retry request. Nothing was dispatched.", true);
        return;
      }
    }
    busy = true; $("launch-button").disabled = true;
    try {
      const run = await api("/api/v1/runs", pending.spec, pending.key);
      selected = run.id;
      sessionStorage.removeItem(pendingKey); pending = null;
      message("Rehearsal started. These fixture steps produce no physics or mining evidence.");
      await refresh();
    } catch (error) {
      message("Launch not confirmed: " + error.message + ". Retry keeps this request, including after reconnect. Free an active slot if required.", true);
    } finally { busy = false; $("launch-button").disabled = false; render(); }
  });
  for (const action of ["pause", "resume", "stop"]) {
    $(action).addEventListener("click", async () => {
      if (busy || !connected || !selected) return;
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
  $("export").addEventListener("click", async () => {
    if (busy || !connected || !selected) return;
    busy = true; render();
    try {
    const run = await api("/api/v1/runs/" + selected);
    const blob = new Blob([JSON.stringify(run, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url;
    anchor.download = "carbon-rehearsal-" + run.id + ".json";
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { message("Export not confirmed: " + error.message, true); }
    finally { busy = false; render(); }
  });
  setInterval(refresh, 1500);
})();
