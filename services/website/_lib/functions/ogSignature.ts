import { createHmac, randomBytes, timingSafeEqual } from 'crypto';

// Signs the text of /api/og preview images, so the endpoint draws only what the site's own pages asked for: no
// one can render their own text on an fm01-branded card, or make the server render endless new images.
// OG_IMAGE_SECRET keeps links valid across restarts and instances. Without it each process has its own key, kept on
// globalThis because Next bundles pages and route handlers into separate copies of this module.
const fallback = globalThis as typeof globalThis & { fm01OgSecret?: string };
const secret = process.env.OG_IMAGE_SECRET || (fallback.fm01OgSecret ??= randomBytes(32).toString('hex'));

export function ogSignature(title: string, description: string): string {
    return createHmac('sha256', secret).update(`${title}\n${description}`).digest('base64url');
}

export function hasValidOgSignature(title: string, description: string, signature: string | null): boolean {
    const expected = Buffer.from(ogSignature(title, description));
    const actual = Buffer.from(signature ?? '');
    return actual.length === expected.length && timingSafeEqual(actual, expected);
}
