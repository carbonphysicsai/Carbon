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
  // The Pilot Designer seals only to a recipient built by `recipient`, from the
  // published key record in data/intake_public_key.json. That page's bytes are
  // pinned by Ask Carbon's public release candidate, so the button reaches the
  // public site only through a new candidate and the owner's approval.
  const SCHEMA = "carbon.intake-sealed.v1";
  const PUBLIC_KEY_SCHEMA = "carbon.intake-key.v1-public";
  const PUBLIC_KEY_FIELDS = ["fingerprint", "key_id", "public_spki", "schema"];
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

  // Recipients this module built. `seal` accepts nothing else, so a key that
  // skipped `recipient`'s checks cannot be sealed to, even when it is valid.
  const issued = new WeakSet();

  /** Seal text to a recipient from `recipient`. Returns the sealed object. */
  async function seal(plaintext, to) {
    if (typeof plaintext !== "string") throw Error("Only text is sealed");
    if (!issued.has(to)) throw Error("Seal only to a recipient built by recipient() from a published key record");
    const publicKey = await subtle().importKey("spki", fromBase64(to.public_spki), { name: "ECDH", namedCurve: "P-256" }, false, []);
    const sender = await subtle().generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
    const salt = root.crypto.getRandomValues(new Uint8Array(32));
    const nonce = root.crypto.getRandomValues(new Uint8Array(12));
    const keyId = to.key_id;
    const key = await derive(sender.privateKey, publicKey, salt);
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

  /**
   * The recipient a client seals to, built from a published key record.
   *
   * The record is closed: a private key file, or a public record carrying
   * anything extra, is refused by name rather than having its public half used.
   * The fingerprint and key identifier are recomputed from the key itself, so
   * the fingerprint a client is shown is always the key's own, never a label
   * that travels beside it.
   */
  async function recipient(record) {
    if (!record || typeof record !== "object" || Array.isArray(record)) throw Error("The intake key record is not an object");
    if ("private_pkcs8" in record) throw Error("This is an intake private key; only the public key record may be published");
    if (record.schema !== PUBLIC_KEY_SCHEMA || Object.keys(record).sort().join() !== PUBLIC_KEY_FIELDS.join())
      throw Error("Not a " + PUBLIC_KEY_SCHEMA + " record");
    await subtle().importKey("spki", fromBase64(record.public_spki), { name: "ECDH", namedCurve: "P-256" }, false, []);
    const computed = await fingerprint(record.public_spki);
    if (record.fingerprint !== computed) throw Error("The intake key record's fingerprint does not match its key");
    if (record.key_id !== (await keyIdOf(record.public_spki))) throw Error("The intake key record's key_id does not match its key");
    const built = Object.freeze({ key_id: record.key_id, fingerprint: computed, public_spki: record.public_spki });
    issued.add(built);
    return built;
  }

  /** The public record for a key pair: the only part that is ever published. */
  const publicRecord = (pair) => ({ schema: PUBLIC_KEY_SCHEMA, key_id: pair.key_id, public_spki: pair.public_spki, fingerprint: pair.fingerprint });

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

  const api = { SCHEMA, PUBLIC_KEY_SCHEMA, fingerprint, generateKeyPair, keyIdOf, open, publicRecord, recipient, seal };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CarbonIntakeSeal = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
