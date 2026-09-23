"use strict";

// E1: archive encryption and key destruction for private client records.
//
// Every client record's content is sealed at rest under a key of its own, and
// the keys live here, in a file apart from the store. Destroying a record's key
// makes every copy of that record unreadable at once — the store file, and any
// backup or archive copy of it — even though those bytes remain. That is what
// lets Carbon describe what deletion actually does instead of promising to
// delete copies it cannot reach.
//
// One key per record, never shared, so no key ever spans two clients. This is
// built to be reviewed: key management is in scope for the security review, and
// the limits are stated in the runbook rather than implied here.
//
// The keyring must not be backed up alongside the store. A backup that holds
// both the ciphertext and its key is a plaintext backup. So the keyring refuses
// to live inside the store's directory, where a "copy the directory" backup
// would take it along.

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const KEYRING_VERSION = "carbon.private-team-intake.archive-keyring.v1";
const SEAL_ALGORITHM = "AES-256-GCM";

class ArchiveKeyDestroyed extends Error {
  constructor(keyId) {
    super("Archive key destroyed; this record's content is unreadable by design");
    this.code = "ARCHIVE_KEY_DESTROYED";
    this.keyId = keyId;
  }
}

function writeDurably(filePath, text) {
  const directory = path.dirname(filePath);
  const temporary = filePath + ".tmp-" + process.pid + "-" + crypto.randomUUID();
  try {
    const handle = fs.openSync(temporary, "wx", 0o600);
    try {
      fs.writeFileSync(handle, text, { encoding: "utf8" });
      fs.fsyncSync(handle);
    } finally {
      fs.closeSync(handle);
    }
    fs.renameSync(temporary, filePath);
  } catch (error) {
    fs.rmSync(temporary, { force: true });
    throw error;
  }
  const directoryHandle = fs.openSync(directory, "r");
  try {
    fs.fsyncSync(directoryHandle);
  } finally {
    fs.closeSync(directoryHandle);
  }
}

const within = (parent, child) => {
  const step = path.relative(parent, child);
  return step === "" || (!step.startsWith("..") && !path.isAbsolute(step));
};

class ArchiveKeyring {
  /**
   * Open (or create) the keyring at `filePath`.
   *
   * `storePath` is the store this keyring serves. The keyring is refused inside
   * that store's directory, because a backup taken by copying the directory
   * would then carry the keys with the ciphertext.
   */
  static open(filePath, { storePath } = {}) {
    if (typeof filePath !== "string" || !path.isAbsolute(filePath))
      throw Error("The archive keyring needs an absolute path");
    const resolved = path.resolve(filePath);
    if (storePath !== undefined && within(path.dirname(path.resolve(storePath)), resolved))
      throw Error(
        "The archive keyring must not live in the store's directory: a backup of " +
          "that directory would carry the keys with the ciphertext",
      );
    fs.mkdirSync(path.dirname(resolved), { recursive: true, mode: 0o700 });
    let state;
    if (fs.existsSync(resolved)) {
      state = JSON.parse(fs.readFileSync(resolved, "utf8"));
      if (!state || state.schema_version !== KEYRING_VERSION || typeof state.keys !== "object" || typeof state.destroyed !== "object")
        throw Error("Invalid archive keyring");
    } else {
      state = { schema_version: KEYRING_VERSION, keys: {}, destroyed: {} };
      writeDurably(resolved, JSON.stringify(state, null, 2) + "\n");
    }
    return new ArchiveKeyring(resolved, state);
  }

  constructor(filePath, state) {
    this.filePath = filePath;
    this.state = state;
  }

  persist() {
    // Merged with the file as it is now, never overwritten from memory alone.
    // Two handles on one keyring would otherwise each write their own view: the
    // later write would drop the other's new keys (a record that can never be
    // read again) or bring back a key the other had destroyed (a deletion
    // quietly undone). Keys are the union, and a destruction always wins.
    let disk = { keys: {}, destroyed: {} };
    if (fs.existsSync(this.filePath)) disk = JSON.parse(fs.readFileSync(this.filePath, "utf8"));
    const destroyed = { ...disk.destroyed, ...this.state.destroyed };
    const keys = Object.fromEntries(
      Object.entries({ ...disk.keys, ...this.state.keys }).filter(([id]) => !destroyed[id]),
    );
    this.state = { schema_version: KEYRING_VERSION, keys, destroyed };
    writeDurably(this.filePath, JSON.stringify(this.state, null, 2) + "\n");
  }

  /** Re-read the keyring, so a key another handle created can be used. */
  refresh() {
    const disk = JSON.parse(fs.readFileSync(this.filePath, "utf8"));
    const destroyed = { ...disk.destroyed, ...this.state.destroyed };
    this.state.destroyed = destroyed;
    this.state.keys = Object.fromEntries(
      Object.entries({ ...disk.keys, ...this.state.keys }).filter(([id]) => !destroyed[id]),
    );
  }

  /** A new key for one record. Durable before it is returned. */
  create() {
    const keyId = "archive-key-" + crypto.randomBytes(16).toString("hex");
    this.state.keys[keyId] = {
      key: crypto.randomBytes(32).toString("base64"),
      created_at: new Date().toISOString(),
    };
    this.persist();
    return keyId;
  }

  status(keyId) {
    if (this.state.keys[keyId]) return "LIVE";
    if (this.state.destroyed[keyId]) return "DESTROYED";
    return "UNKNOWN";
  }

  material(keyId) {
    if (!this.state.keys[keyId] && !this.state.destroyed[keyId]) this.refresh();
    const entry = this.state.keys[keyId];
    if (!entry) {
      if (this.state.destroyed[keyId]) throw new ArchiveKeyDestroyed(keyId);
      throw Error("Unknown archive key " + keyId);
    }
    return Buffer.from(entry.key, "base64");
  }

  /** Seal a value under `keyId`, bound to `context` so it cannot be moved. */
  seal(keyId, value, context) {
    const nonce = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv("aes-256-gcm", this.material(keyId), nonce);
    cipher.setAAD(Buffer.from(context, "utf8"));
    const ciphertext = Buffer.concat([cipher.update(JSON.stringify(value), "utf8"), cipher.final()]);
    return {
      algorithm: SEAL_ALGORITHM,
      key_id: keyId,
      nonce: nonce.toString("base64"),
      ciphertext: ciphertext.toString("base64"),
      tag: cipher.getAuthTag().toString("base64"),
    };
  }

  /** Open a sealed value, or throw ArchiveKeyDestroyed if its key is gone. */
  open(envelope, context) {
    if (!envelope || envelope.algorithm !== SEAL_ALGORITHM) throw Error("Unsupported sealed record");
    const decipher = crypto.createDecipheriv(
      "aes-256-gcm",
      this.material(envelope.key_id),
      Buffer.from(envelope.nonce, "base64"),
    );
    decipher.setAAD(Buffer.from(context, "utf8"));
    decipher.setAuthTag(Buffer.from(envelope.tag, "base64"));
    const plaintext = Buffer.concat([
      decipher.update(Buffer.from(envelope.ciphertext, "base64")),
      decipher.final(),
    ]);
    return JSON.parse(plaintext.toString("utf8"));
  }

  /**
   * Destroy a key. The material is removed and a tombstone kept, durably,
   * before this returns. Every copy sealed under it is then unreadable.
   */
  destroy(keyId, { reason } = {}) {
    // A key another handle created is not in this handle's memory yet; it is
    // re-read rather than refused, or an approved deletion would fail to reach it.
    if (!this.state.keys[keyId] && !this.state.destroyed[keyId]) this.refresh();
    if (!this.state.keys[keyId]) {
      if (this.state.destroyed[keyId]) return this.state.destroyed[keyId];
      throw Error("Unknown archive key " + keyId);
    }
    delete this.state.keys[keyId];
    this.state.destroyed[keyId] = { destroyed_at: new Date().toISOString(), reason: reason || null };
    this.persist();
    return this.state.destroyed[keyId];
  }
}

module.exports = { ArchiveKeyDestroyed, ArchiveKeyring, KEYRING_VERSION, SEAL_ALGORITHM };
