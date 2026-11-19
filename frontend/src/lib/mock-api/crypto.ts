/**
 * Development-only password hashing using the browser Web Crypto API (PBKDF2 + per-account salt).
 * IMPORTANT: Client-side hashing is ONLY a development simulation and never replaces
 * server-side Argon2id or bcrypt password hashing.
 */

const ITERATIONS = 10_000;

function toHex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function fromHex(hex: string): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(new ArrayBuffer(hex.length / 2));
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = Number.parseInt(hex.slice(i, i + 2), 16);
  }
  return bytes;
}

export function generateSalt(): string {
  const buf = new Uint8Array(16);
  crypto.getRandomValues(buf);
  return toHex(buf);
}

export function generateMockToken(userId: string): string {
  const buf = new Uint8Array(16);
  crypto.getRandomValues(buf);
  return `nexus_mock_tok_${userId}_${toHex(buf)}`;
}

export async function hashPassword(password: string, saltHex: string): Promise<string> {
  const encoder = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    encoder.encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const derived = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      salt: fromHex(saltHex),
      iterations: ITERATIONS,
      hash: "SHA-256",
    },
    keyMaterial,
    256,
  );
  return toHex(new Uint8Array(derived));
}

export async function verifyPassword(
  password: string,
  saltHex: string,
  expectedHash: string,
): Promise<boolean> {
  const actual = await hashPassword(password, saltHex);
  return actual === expectedHash;
}

