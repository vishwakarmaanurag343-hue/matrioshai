/**
 * Lossless markdown intent block parser (frontend mirror).
 *
 * Round-trip rules:
 * - If the block is missing, the body is unchanged and intents is [].
 * - If the block is malformed, it is dropped; the body is returned; the
 *   caller should surface a warning toast. The note must still load.
 * - A note with zero Intents is byte-identical to a note with no block.
 */

const BLOCK_TRAILING: RegExp =
  /\n*<!--\s*matrioshai:intents\s+v1\s*\n\[[\s\S]*?\]\n\s*-->\s*$/;

const BLOCK_FULL: RegExp =
  /<!--\s*matrioshai:intents\s+v1\s*\n(?<body>\[[\s\S]*?\])\n\s*-->\s*$/;

export interface IntentParseResult {
  cleanBody: string;
  intents: any[];
  hadMalformedBlock: boolean;
}

export function splitBodyAndIntents(markdown: string | null | undefined): IntentParseResult {
  if (!markdown) {
    return { cleanBody: "", intents: [], hadMalformedBlock: false };
  }

  const match = markdown.match(BLOCK_FULL);
  if (!match || !match.groups) {
    return { cleanBody: markdown, intents: [], hadMalformedBlock: false };
  }

  const bodyText = match.groups.body;
  let intents: any[] = [];
  let hadMalformed = false;
  try {
    const parsed = JSON.parse(bodyText);
    if (Array.isArray(parsed)) {
      intents = parsed.filter((x) => x && typeof x === "object");
    } else {
      hadMalformed = true;
    }
  } catch {
    hadMalformed = true;
  }

  const cleanBody = markdown.replace(BLOCK_TRAILING, "");
  return { cleanBody, intents, hadMalformedBlock: hadMalformed };
}

export function serializeIntentBlock(intents: any[]): string {
  if (!intents || intents.length === 0) {
    return "";
  }
  const body = JSON.stringify(intents);
  return `\n<!-- matrioshai:intents v1\n${body}\n-->\n`;
}

export function writeNoteWithIntents(markdownBody: string, intents: any[]): string {
  const { cleanBody } = splitBodyAndIntents(markdownBody);
  const block = serializeIntentBlock(intents);
  if (!block) {
    return cleanBody;
  }
  return cleanBody.replace(/\n+$/, "") + block;
}
