"use strict";
// A small QR encoder for the Control Center: byte mode, error correction L,
// versions 1 to 5 (up to 106 bytes), one data block, a fixed mask. It exists so
// the "Fund your wallet" step can show a money-key address as a QR code with
// nothing fetched from anywhere and no third-party code. The address it encodes
// is public; nothing here touches a key.
//
// `encode(text)` returns {size, modules} where modules[row][col] is true for a
// dark module; it throws if the text does not fit. `svg(text)` returns an SVG
// string with a four-module quiet zone. Both are pure, so a test can decode them.
(function (root) {
  // Version -> [data codewords, error-correction codewords] at level L, one block.
  const SPEC = {1: [19, 7], 2: [34, 10], 3: [55, 15], 4: [80, 20], 5: [108, 26]};
  const ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30]};
  const MASK = 0;

  // GF(256) with the QR polynomial 0x11d.
  const EXP = new Array(512), LOG = new Array(256);
  (function () {
    let x = 1;
    for (let i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 256) x ^= 0x11d; }
    for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
  })();
  const mul = (a, b) => (a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]]);

  function remainder(data, ecLength) {
    let generator = [1];
    for (let i = 0; i < ecLength; i++) {
      const next = new Array(generator.length + 1).fill(0);
      for (let j = 0; j < generator.length; j++) {
        next[j] ^= generator[j];
        next[j + 1] ^= mul(generator[j], EXP[i]);
      }
      generator = next;
    }
    const result = new Array(ecLength).fill(0);
    for (const byte of data) {
      const factor = byte ^ result.shift();
      result.push(0);
      for (let i = 0; i < ecLength; i++) result[i] ^= mul(generator[i + 1], factor);
    }
    return result;
  }

  function utf8(text) {
    const bytes = [];
    for (const char of unescape(encodeURIComponent(String(text)))) bytes.push(char.charCodeAt(0));
    return bytes;
  }

  function codewords(bytes, version) {
    const [dataLength] = SPEC[version];
    const bits = [];
    const push = (value, count) => { for (let i = count - 1; i >= 0; i--) bits.push((value >>> i) & 1); };
    push(0b0100, 4);
    push(bytes.length, 8);
    for (const byte of bytes) push(byte, 8);
    const capacity = dataLength * 8;
    push(0, Math.min(4, capacity - bits.length));
    while (bits.length % 8) bits.push(0);
    const words = [];
    for (let i = 0; i < bits.length; i += 8) words.push(parseInt(bits.slice(i, i + 8).join(""), 2));
    for (let pad = 0; words.length < dataLength; pad++) words.push(pad % 2 ? 0x11 : 0xec);
    return words.concat(remainder(words, SPEC[version][1]));
  }

  function formatBits() {
    // Level L is 01; five data bits, BCH(15,5), then the standard mask.
    let value = (0b01 << 3) | MASK;
    let bch = value << 10;
    for (let i = 14; i >= 10; i--) if ((bch >>> i) & 1) bch ^= 0x537 << (i - 10);
    return ((value << 10) | bch) ^ 0x5412;
  }

  function encode(text) {
    const bytes = utf8(text);
    let version = 0;
    for (const v of [1, 2, 3, 4, 5]) if (bytes.length <= SPEC[v][0] - 2) { version = v; break; }
    if (!version) throw new Error("qr: text too long");
    const size = 17 + 4 * version;
    const modules = Array.from({length: size}, () => new Array(size).fill(false));
    const reserved = Array.from({length: size}, () => new Array(size).fill(false));
    const set = (r, c, dark) => { modules[r][c] = dark; reserved[r][c] = true; };

    const finder = (r0, c0) => {
      for (let dr = -1; dr <= 7; dr++) for (let dc = -1; dc <= 7; dc++) {
        const r = r0 + dr, c = c0 + dc;
        if (r < 0 || c < 0 || r >= size || c >= size) continue;
        const inside = dr >= 0 && dr <= 6 && dc >= 0 && dc <= 6;
        const dark = inside && (dr === 0 || dr === 6 || dc === 0 || dc === 6 || (dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4));
        set(r, c, dark);
      }
    };
    finder(0, 0); finder(0, size - 7); finder(size - 7, 0);
    for (let i = 8; i < size - 8; i++) { set(6, i, i % 2 === 0); set(i, 6, i % 2 === 0); }
    const centres = ALIGN[version];
    for (const r of centres) for (const c of centres) {
      if (reserved[r][c]) continue;
      for (let dr = -2; dr <= 2; dr++) for (let dc = -2; dc <= 2; dc++) {
        set(r + dr, c + dc, Math.max(Math.abs(dr), Math.abs(dc)) !== 1);
      }
    }
    set(size - 8, 8, true); // the dark module
    // Reserve the format areas; they are written after the data.
    for (let i = 0; i < 9; i++) { reserved[8][i] = true; reserved[i][8] = true; }
    for (let i = 0; i < 8; i++) { reserved[8][size - 1 - i] = true; reserved[size - 1 - i][8] = true; }

    // Data, zig-zag from the bottom right in column pairs, skipping the timing column.
    const words = codewords(bytes, version);
    const bits = [];
    for (const word of words) for (let i = 7; i >= 0; i--) bits.push((word >>> i) & 1);
    let index = 0, upward = true;
    for (let col = size - 1; col > 0; col -= 2) {
      if (col === 6) col--;
      for (let step = 0; step < size; step++) {
        const r = upward ? size - 1 - step : step;
        for (let k = 0; k < 2; k++) {
          const c = col - k;
          if (reserved[r][c]) continue;
          let dark = index < bits.length ? bits[index] === 1 : false;
          index++;
          if ((r + c) % 2 === 0) dark = !dark; // mask 0
          modules[r][c] = dark;
        }
      }
      upward = !upward;
    }

    // Format information, both copies.
    const format = formatBits();
    const bit = i => ((format >>> i) & 1) === 1;
    for (let i = 0; i <= 5; i++) modules[i][8] = bit(i);
    modules[7][8] = bit(6); modules[8][8] = bit(7); modules[8][7] = bit(8);
    for (let i = 9; i < 15; i++) modules[8][14 - i] = bit(i);
    for (let i = 0; i < 8; i++) modules[8][size - 1 - i] = bit(i);
    for (let i = 8; i < 15; i++) modules[size - 15 + i][8] = bit(i);
    return {size, modules, version};
  }

  function svg(text, scale) {
    const {size, modules} = encode(text);
    const unit = scale || 4, quiet = 4, side = (size + 2 * quiet) * unit;
    let path = "";
    for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) {
      if (modules[r][c]) path += "M" + (c + quiet) * unit + " " + (r + quiet) * unit + "h" + unit + "v" + unit + "h-" + unit + "z";
    }
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + side + " " + side + '" width="' + side + '" height="' + side + '" shape-rendering="crispEdges" role="img">' +
      '<rect width="100%" height="100%" fill="#fff"/><path d="' + path + '" fill="#000"/></svg>';
  }

  const api = {encode, svg};
  root.CarbonQr = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
