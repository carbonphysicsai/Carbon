"use strict";
// The Control Center's QR code, drawn locally from the vendored qrcode-generator (MIT, see THIRD_PARTY.md): byte mode,
// error correction L. `encode(text)` returns {size, modules, version}, modules[row][col] true for a dark module; it
// throws if the text does not fit. Pure, so a test can decode it. The address it encodes is public; nothing here
// touches a key and nothing is fetched.
(function (root) {
  const generator = typeof module !== "undefined" && module.exports && typeof require === "function" ? require("./qrcode_generator.js") : root.qrcode;
  function encode(text) {
    if (typeof generator !== "function") throw new Error("qr: generator missing");
    const qr = generator(0, "L");
    qr.addData(String(text), "Byte");
    try { qr.make(); } catch (error) { throw new Error("qr: text too long"); }
    const size = qr.getModuleCount();
    if (size > 37) throw new Error("qr: text too long"); // an address is far smaller than version 5 (106 bytes)
    const modules = [];
    for (let r = 0; r < size; r++) { const row = []; for (let c = 0; c < size; c++) row.push(Boolean(qr.isDark(r, c))); modules.push(row); }
    return {size, modules, version: (size - 17) / 4};
  }
  const api = {encode};
  root.CarbonQr = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
