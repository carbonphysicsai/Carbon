# E6: encrypting the package before it is sent — a proposal

Status: **proposed, not implemented.** This is the only part of E6 that asks
someone outside Carbon to do something, so it waits for the owner. Nothing here
changes the public Pilot Designer until the owner has seen the client steps.

The goal, from the counsel brief: the package a client mails to Carbon is
ciphertext in transit and in the mailbox, so the mail provider only ever holds
ciphertext, even before the transport copy is deleted.

## (a) The format — what a client actually does

**Recommendation: encrypt in the browser, inside the Pilot Designer the client
already uses to make the package.** Add one button, *Download encrypted for
Carbon*. The page encrypts the reviewed package to Carbon's intake public key
before it is saved, and the client emails the resulting file.

The client already produces the package in that page, which runs on their own
machine, so this adds one click and no install. The encryption is standard
WebCrypto, available in every current browser: an ephemeral ECDH P-256 key
agreement, HKDF-SHA-256, and AES-256-GCM, in an HPKE-style construction. The
file carries the key identifier it was encrypted to, so a rotated key is
handled without guessing.

What the client would be told to do:

1. Fill in the Pilot Designer as now.
2. Press **Download encrypted for Carbon**.
3. Check that the key fingerprint shown under the button matches the
   fingerprint printed in the Data Handling Statement attached to their NDA.
4. Attach the downloaded `.carbon-sealed` file to an email to the intake
   address. Nothing else goes in the email.

The friction, honestly:

- **Almost none for a client who uses the Pilot Designer.** Step 3 is the only
  new judgement they make. Most will skip it, which is why (d) does not rely on
  them doing it.
- **The client cannot read the encrypted file back.** If they want a copy of
  what they sent, they keep the ordinary download as well, and that copy is
  theirs.
- **A client whose policy forbids running a vendor's page on their data** needs
  a fallback. Proposed: OpenPGP, meaning Kleopatra or `gpg`, with Carbon's
  OpenPGP public key. This is heavier. It means installing software, importing
  a key and choosing the recipient, and many engineering teams will have to ask
  their IT department first. Offer it only on request.
- **Not recommended:** password-protected ZIP or 7-Zip archives. These are
  familiar, but the password then has to travel by another channel, is chosen by
  a person, and is a shared secret rather than a public key. Also not
  recommended: S/MIME, which needs certificates on the client's side.

## (b) The key, and who holds it

- **One intake key pair.** The private key lives on the internal machine, where
  relaying and decryption happen. It is stored like the archive keyring: a
  `0600` file outside the store's directory, and never in the mailbox, the
  repository or a browser.
- **Both receivers can decrypt,** because both relay from that machine through
  the receiver's own tooling. Mailbox delegation gives them the ciphertext.
  Only the internal machine turns it into plaintext.
- **Backup:** one offline copy of the private key, encrypted under a
  passphrase kept in the owner's password manager. Restoring it is a documented
  owner action.
- **Rotation:** generate a new pair and publish its fingerprint as in (d). Keep
  the old private key only until every package encrypted to it has been
  relayed, then destroy it. Because each package names its key, a package that
  arrives late under the old key is recognised, not mis-decrypted.
- **Review:** key management for this key joins the E1 archive keys in the
  security review's scope, and is handled the same way, not separately.

## (c) When a client sends plaintext anyway

They will. **Proposed defined action: relay it; record that it arrived in
plaintext; permanently remove the transport copy at once; and reply to the
client with the encryption steps for next time.**

The exposure has already happened by the time anyone sees the message. Refusing
the package would delay the client without undoing anything, and asking them to
resend encrypted adds a second copy to the mailbox. Relaying and then removing
the plaintext copy immediately shortens how long it exists.

**This is built:** the relay states `x-carbon-transport-arrival: PLAINTEXT`, and
the record then carries `required_disposition:
PERMANENTLY_REMOVED_WITHOUT_DELAY`. The reply to the client is a human step,
and it waits on the owner's approval of this proposal.

## (d) Publishing the public key

A key taken from an unauthenticated page is weaker than it looks. So there are
two channels, and they check each other:

- **The key is embedded in the Pilot Designer page,** served over HTTPS from
  Carbon's own domain. It has the same authenticity as the page the client is
  already trusting with their data.
- **The fingerprint is printed in the Data Handling Statement attached to the
  signed scoping NDA,** a document the client receives through a different
  channel and signs. A client or their IT department can compare the two.

The owner confirms the fingerprint when the key is published, and again at
each rotation, before the statement is updated.

## What deciding this would take

1. Approve or amend the recommended format and the client steps in (a).
2. Approve the plaintext-arrival action in (c), including the reply to the
   client.
3. Decide who generates the key pair and where its offline backup is kept.

Until then, mailed packages relay as they are, and the record states honestly
whether each one arrived `ENCRYPTED` or `PLAINTEXT`.
