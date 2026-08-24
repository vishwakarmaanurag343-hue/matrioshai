import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Generate a valid PNG buffer of size x size with stylized MATRIOSHAI icon.
 * Background: Dark purple/indigo #1e1b4b (30, 27, 75)
 * Accent/Logo: Bright cyan/violet stylized 'M'
 */
function createPngBuffer(width, height) {
  // RGBA pixel buffer (width * height * 4)
  const rowSize = width * 4;
  const rawData = Buffer.alloc((rowSize + 1) * height);

  for (let y = 0; y < height; y++) {
    const rowOffset = y * (rowSize + 1);
    rawData[rowOffset] = 0; // Filter byte: None

    for (let x = 0; x < width; x++) {
      const pxOffset = rowOffset + 1 + x * 4;

      // Normalized coordinates [0, 1]
      const nx = x / width;
      const ny = y / height;

      // Distance from center
      const dx = nx - 0.5;
      const dy = ny - 0.5;
      const dist = Math.sqrt(dx * dx + dy * dy);

      // Rounded rectangle / badge mask
      const inBadge = dist <= 0.46;

      if (!inBadge) {
        // Transparent
        rawData[pxOffset] = 0;
        rawData[pxOffset + 1] = 0;
        rawData[pxOffset + 2] = 0;
        rawData[pxOffset + 3] = 0;
        continue;
      }

      // Background gradient: #0f172a to #4338ca (Deep Slate to Indigo)
      let r = Math.round(15 + nx * 50);
      let g = Math.round(23 + ny * 35);
      let b = Math.round(42 + (1 - ny) * 160);
      let a = 255;

      // Stylized 'M' symbol in center
      // Normalize to [-1, 1] inside badge
      const mx = (nx - 0.5) * 2;
      const my = (ny - 0.5) * 2;

      // Left bar: mx between -0.6 and -0.3, my between -0.4 and 0.45
      const inLeftBar = mx >= -0.55 && mx <= -0.32 && my >= -0.45 && my <= 0.45;
      // Right bar: mx between 0.32 and 0.55, my between -0.45 and 0.45
      const inRightBar = mx >= 0.32 && mx <= 0.55 && my >= -0.45 && my <= 0.45;
      // Left diagonal: from (-0.35, -0.45) to (0.0, 0.15)
      const inLeftDiag = my >= -0.45 && my <= 0.25 && Math.abs(my - (mx * 1.5 + 0.1)) < 0.18 && mx >= -0.45 && mx <= 0.05;
      // Right diagonal: from (0.0, 0.15) to (0.35, -0.45)
      const inRightDiag = my >= -0.45 && my <= 0.25 && Math.abs(my - (-mx * 1.5 + 0.1)) < 0.18 && mx >= -0.05 && mx <= 0.45;

      if (inLeftBar || inRightBar || inLeftDiag || inRightDiag) {
        // Cyan / Electric Blue highlight (#38bdf8 to #a855f7)
        r = Math.round(56 + nx * 110);
        g = Math.round(189 - ny * 100);
        b = Math.round(248 + ny * 5);
      }

      // Border ring glow
      if (dist >= 0.42 && dist <= 0.46) {
        r = 99;
        g = 102;
        b = 241;
      }

      rawData[pxOffset] = r;
      rawData[pxOffset + 1] = g;
      rawData[pxOffset + 2] = b;
      rawData[pxOffset + 3] = a;
    }
  }

  // Compress raw pixel data using zlib deflate
  const compressed = zlib.deflateSync(rawData);

  // Build PNG Chunks
  const signature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

  // IHDR chunk
  const ihdrData = Buffer.alloc(13);
  ihdrData.writeUInt32BE(width, 0);
  ihdrData.writeUInt32BE(height, 4);
  ihdrData[8] = 8; // Bit depth: 8
  ihdrData[9] = 6; // Color type: 6 (RGBA)
  ihdrData[10] = 0; // Compression method: 0
  ihdrData[11] = 0; // Filter method: 0
  ihdrData[12] = 0; // Interlace method: 0
  const ihdrChunk = createChunk('IHDR', ihdrData);

  // IDAT chunk
  const idatChunk = createChunk('IDAT', compressed);

  // IEND chunk
  const iendChunk = createChunk('IEND', Buffer.alloc(0));

  return Buffer.concat([signature, ihdrChunk, idatChunk, iendChunk]);
}

function createChunk(type, data) {
  const length = data.length;
  const chunk = Buffer.alloc(8 + length + 4);
  chunk.writeUInt32BE(length, 0);
  chunk.write(type, 4, 4, 'ascii');
  data.copy(chunk, 8);

  const crcTarget = chunk.subarray(4, 8 + length);
  const crcValue = crc32(crcTarget);
  chunk.writeUInt32BE(crcValue, 8 + length);

  return chunk;
}

// CRC32 implementation for PNG chunks
const crcTable = [];
for (let n = 0; n < 256; n++) {
  let c = n;
  for (let k = 0; k < 8; k++) {
    if (c & 1) c = 0xedb88320 ^ (c >>> 1);
    else c = c >>> 1;
  }
  crcTable[n] = c;
}

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  }
  return (c ^ 0xffffffff) >>> 0;
}

// Ensure output directories exist
const assetsDir = path.resolve(__dirname, '../assets/icons');
fs.mkdirSync(assetsDir, { recursive: true });

const sizes = [16, 48, 128];
for (const size of sizes) {
  const iconPath = path.join(assetsDir, `icon-${size}.png`);
  const pngBuf = createPngBuffer(size, size);
  fs.writeFileSync(iconPath, pngBuf);
  console.log(`Generated icon: ${iconPath} (${pngBuf.length} bytes)`);
}
