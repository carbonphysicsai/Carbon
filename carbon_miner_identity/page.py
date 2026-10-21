"""The helper's own page: plain words, five steps, no third-party code, no storage, no copy button."""

INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer"><title>Create my mining identity</title>
<style>
body{font:17px/1.5 system-ui,sans-serif;max-width:640px;margin:32px auto;padding:0 16px;color:#111;background:#fafaf7}
h1{font-size:26px}button{font:inherit;padding:12px 20px;border:1px solid #111;background:#111;color:#fff;cursor:pointer}
button.quiet{background:transparent;color:#111}input{font:inherit;padding:10px;width:100%;box-sizing:border-box;margin:6px 0 14px}
.phrase{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:16px 0;padding:16px;border:2px solid #111;
user-select:none;-webkit-user-select:none}.phrase span{padding:4px 6px}.warn{border-left:4px solid #b00;padding:8px 12px;background:#fff3f0}
.err{color:#b00}.hint{color:#555;font-size:15px}[hidden]{display:none}
</style></head><body>
<h1>Create my mining identity</h1>
<p class="hint">This window runs only on your computer. Carbon never sees your keys, your recovery phrase or your password.</p>
<p id="error" class="err" role="alert"></p>

<section id="s-name">
<h2>1. Name it</h2>
<label for="name">A name for this wallet (letters, digits, - or _)</label><input id="name" autocomplete="off" spellcheck="false">
<button id="make">Create</button>
</section>

<section id="s-phrase" hidden>
<h2>2. Write down your recovery phrase</h2>
<p class="warn"><strong>Write these 12 words on paper, in order.</strong> They are the only way to get your funds back if you lose
your password or this computer. Anyone who has them can take your funds. Carbon cannot recover them for you, and this page
will not show them again. Do not photograph them or keep them in a file.</p>
<div id="phrase" class="phrase"></div>
<button id="written">I have written them down</button>
</section>

<section id="s-confirm" hidden>
<h2>3. Check you wrote it down right</h2>
<p>The words are hidden now. Type the words you were asked for.</p>
<div id="asks"></div>
<button id="check">Check</button>
</section>

<section id="s-password" hidden>
<h2>4. Choose two passwords</h2>
<p class="hint">Two keys, two passwords, and they must differ. At least 10 characters each.</p>
<p><strong>Money password (coldkey).</strong> Guards your funds. You type it rarely, so make it long and keep it safe. If you forget it, your recovery phrase is the way back.</p>
<label for="cpw">Money password</label><input id="cpw" type="password" autocomplete="new-password">
<label for="cpw2">Type it again</label><input id="cpw2" type="password" autocomplete="new-password">
<p><strong>Mining password (hotkey).</strong> Unlocks the key that signs your mining work. You type it each time you start your signer. It cannot move your funds.</p>
<label for="hpw">Mining password</label><input id="hpw" type="password" autocomplete="new-password">
<label for="hpw2">Type it again</label><input id="hpw2" type="password" autocomplete="new-password">
<button id="save">Save my identity</button>
</section>

<section id="s-done" hidden>
<h2>5. Done</h2>
<p>Your identity is saved on this computer, each key locked with its own password.</p>
<p>Your hotkey address (public, safe to share). Copy it into the Control Center's setup:</p>
<p><code id="hot"></code></p>
<p class="hint">Your coldkey address (public): <code id="cold"></code></p>
<p class="warn"><strong>Back up this folder.</strong> Your hotkey has no recovery phrase: if this computer is lost, only a copy of the wallet folder brings it back (it stays locked by your mining password): <code id="folder"></code></p>
<p><strong>Next:</strong> joining the subnet is paid from your own coldkey, in your own wallet tool; Carbon neither charges nor
receives it. Then start your signer in a terminal: it asks for your password there.</p>
<button id="close" class="quiet">Close this window</button>
</section>
<script src="/helper.js"></script></body></html>
"""

HELPER_JS = r"""
"use strict";
(() => {
  // The one-time token is in the address fragment: read it, then remove it from the address bar.
  const match = /^#t=([A-Za-z0-9_-]{20,128})$/.exec(location.hash);
  const token = match ? match[1] : "";
  history.replaceState(null, "", location.pathname);
  const $ = id => document.getElementById(id);
  const show = id => { for (const s of document.querySelectorAll("section")) s.hidden = s.id !== id; $("error").textContent = ""; };
  let busy = false;
  async function call(path, body) {
    if (busy) return null;
    busy = true;
    try {
      const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json", "X-Identity-Token": token},
        body: JSON.stringify(body || {}), cache: "no-store", referrerPolicy: "no-referrer", credentials: "omit"});
      const result = await response.json();
      if (!response.ok) { $("error").textContent = result.error === "token_required" ? "This link has expired. Start the helper again." : (result.error || "Something went wrong."); return null; }
      return result;
    } catch (_) { $("error").textContent = "The helper is not running. Start it again."; return null; }
    finally { busy = false; }
  }
  if (!token) $("error").textContent = "Open the link the helper printed in your terminal.";
  $("make").addEventListener("click", async () => {
    const made = await call("/api/create", {name: $("name").value.trim()});
    if (!made) return;
    const grid = $("phrase"); grid.replaceChildren();
    made.words.forEach((word, i) => { const cell = document.createElement("span"); cell.textContent = (i + 1) + ". " + word; grid.append(cell); });
    const asks = $("asks"); asks.replaceChildren();
    for (const position of made.ask) {
      const label = document.createElement("label"); label.textContent = "Word number " + position;
      const input = document.createElement("input"); input.autocomplete = "off"; input.spellcheck = false; input.dataset.ask = String(position);
      asks.append(label, input);
    }
    show("s-phrase");
  });
  $("written").addEventListener("click", () => { $("phrase").replaceChildren(); show("s-confirm"); });
  $("check").addEventListener("click", async () => {
    const words = [...document.querySelectorAll("#asks input")].map(input => input.value);
    const ok = await call("/api/confirm", {words});
    if (!ok) return;
    for (const input of document.querySelectorAll("#asks input")) input.value = "";
    show("s-password");
  });
  $("save").addEventListener("click", async () => {
    const saved = await call("/api/save", {coldkey_password: $("cpw").value, coldkey_again: $("cpw2").value, hotkey_password: $("hpw").value, hotkey_again: $("hpw2").value});
    for (const id of ["cpw", "cpw2", "hpw", "hpw2"]) $(id).value = "";
    if (!saved) return;
    $("hot").textContent = saved.hotkey_address; $("cold").textContent = saved.coldkey_address; $("folder").textContent = saved.folder;
    show("s-done");
  });
  $("close").addEventListener("click", async () => { await call("/api/done"); document.body.replaceChildren("You can close this window now."); });
})();
"""
