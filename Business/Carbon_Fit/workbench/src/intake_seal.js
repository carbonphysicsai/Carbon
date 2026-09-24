(function (root) {
  "use strict";
  // E6, decision 2 (owner-delegated, 2026-09-23): a client seals the reviewed
  // package to Carbon's intake public key before mailing it, so the mail
  // provider only ever holds ciphertext.
  //
  // One implementation for the browser and the receiver: WebCrypto only, which
  // every current browser and Node provide. ECDH on P-256 with a fresh sender
  // key per package, HKDF-SHA-256, AES-256-GCM. The sealed file names the key
  // it was sealed to by fingerprint, so a rotated key is recognised rather than
  // tried and failed.
  //
  // Not wired into the public Pilot Designer. That page's bytes are pinned by
  // Ask Carbon's public release candidate, and the button waits for the owner to
  // generate the real intake key and approve a new candidate.
  const SCHEMA = "carbon.intake-sealed.v1";
  const INFO = new TextEncoder().encode(SCHEMA);
  const subtle = () => {
    const api = root.crypto && root.crypto.subtle;
    if (!api) throw Error("WebCrypto is unavailable in this environment");
    return api;
  };
  const toBase64 = (bytes) => {
    let text = "";
    for (const byte of new Uint8Array(bytes)) text += String.fromCharCode(byte);
    return btoa(text);
  };
  const fromBase64 = (text) => {
    if (typeof text !== "string" || !/^[A-Za-z0-9+/]+={0,2}$/.test(text)) throw Error("Invalid sealed package encoding");
    return Uint8Array.from(atob(text), (char) => char.charCodeAt(0));
  };
  const hex = (bytes) => Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");

  /** The fingerprint a client compares against the one printed in their NDA. */
  async function fingerprint(spkiBase64) {
    const digest = await subtle().digest("SHA-256", fromBase64(spkiBase64));
    return hex(digest).match(/.{4}/g).slice(0, 16).join(" ");
  }
  const keyIdOf = async (spkiBase64) => "intake-key-" + (await fingerprint(spkiBase64)).replace(/ /g, "").slice(0, 32);
  const aad = (keyId) => new TextEncoder().encode(SCHEMA + "\n" + keyId);

  async function derive(privateKey, publicKey, salt) {
    const shared = await subtle().deriveBits({ name: "ECDH", public: publicKey }, privateKey, 256);
    const material = await subtle().importKey("raw", shared, "HKDF", false, ["deriveKey"]);
    return subtle().deriveKey(
      { name: "HKDF", hash: "SHA-256", salt, info: INFO },
      material,
      { name: "AES-GCM", length: 256 },
      false,
      ["encrypt", "decrypt"],
    );
  }

  /** Seal text to the intake public key (SPKI, base64). Returns the sealed object. */
  async function seal(plaintext, recipientSpkiBase64) {
    if (typeof plaintext !== "string") throw Error("Only text is sealed");
    const recipient = await subtle().importKey("spki", fromBase64(recipientSpkiBase64), { name: "ECDH", namedCurve: "P-256" }, false, []);
    const sender = await subtle().generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
    const salt = root.crypto.getRandomValues(new Uint8Array(32));
    const nonce = root.crypto.getRandomValues(new Uint8Array(12));
    const keyId = await keyIdOf(recipientSpkiBase64);
    const key = await derive(sender.privateKey, recipient, salt);
    const ciphertext = await subtle().encrypt({ name: "AES-GCM", iv: nonce, additionalData: aad(keyId) }, key, new TextEncoder().encode(plaintext));
    return {
      schema: SCHEMA,
      key_id: keyId,
      sender_public: toBase64(await subtle().exportKey("raw", sender.publicKey)),
      salt: toBase64(salt),
      nonce: toBase64(nonce),
      ciphertext: toBase64(ciphertext),
    };
  }

  /**
   * Open a sealed object with the intake private key (PKCS#8, base64) and its
   * public key (SPKI, base64). Refuses one sealed to a different key by name.
   */
  async function open(sealed, privatePkcs8Base64, publicSpkiBase64) {
    const fields = ["schema", "key_id", "sender_public", "salt", "nonce", "ciphertext"];
    if (!sealed || typeof sealed !== "object" || Object.keys(sealed).sort().join() !== [...fields].sort().join() || sealed.schema !== SCHEMA)
      throw Error("Not a " + SCHEMA + " package");
    const keyId = await keyIdOf(publicSpkiBase64);
    if (sealed.key_id !== keyId)
      throw Error("This package was sealed to " + sealed.key_id + ", not to the configured intake key " + keyId);
    const privateKey = await subtle().importKey("pkcs8", fromBase64(privatePkcs8Base64), { name: "ECDH", namedCurve: "P-256" }, false, ["deriveBits"]);
    const sender = await subtle().importKey("raw", fromBase64(sealed.sender_public), { name: "ECDH", namedCurve: "P-256" }, false, []);
    const key = await derive(privateKey, sender, fromBase64(sealed.salt));
    let plaintext;
    try {
      plaintext = await subtle().decrypt({ name: "AES-GCM", iv: fromBase64(sealed.nonce), additionalData: aad(sealed.key_id) }, key, fromBase64(sealed.ciphertext));
    } catch {
      throw Error("The sealed package does not authenticate: it was altered, or sealed to another key");
    }
    return new TextDecoder().decode(plaintext);
  }

  /** A new intake key pair, for the owner's key tool. */
  async function generateKeyPair() {
    const pair = await subtle().generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
    const publicSpki = toBase64(await subtle().exportKey("spki", pair.publicKey));
    return {
      public_spki: publicSpki,
      private_pkcs8: toBase64(await subtle().exportKey("pkcs8", pair.privateKey)),
      key_id: await keyIdOf(publicSpki),
      fingerprint: await fingerprint(publicSpki),
    };
  }

  const api = { SCHEMA, fingerprint, generateKeyPair, keyIdOf, open, seal };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CarbonIntakeSeal = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
