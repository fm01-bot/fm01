import en from '@shared/localization/responses/en.l10n.json'
import hu from '@shared/localization/responses/hu.l10n.json'

/**
 * The bot's own response texts (`shared/localization/responses/<lang>.l10n.json`), bundled at
 * build time. Showcase messages point at them by exact key (`"botResponse": "mod.warn.response"`),
 * so the site always shows what the bot really sends.
 */
const RESPONSES: Record<string, unknown> = { en, hu }

/** The bot's source language: used when a key is missing in the requested locale. */
export const FALLBACK_LOCALE = 'en'

export function getPathValue(value: unknown, key: string): unknown {
    return key.split('.').reduce<unknown>((current, part) => {
        if (typeof current !== 'object' || current === null || Array.isArray(current)) return undefined
        return (current as Record<string, unknown>)[part]
    }, value)
}

/** Looks `key` up in `locale`'s bot responses, falling back to English. */
export function getResponse(locale: string, key: string): unknown {
    return getPathValue(RESPONSES[locale], key) ?? getPathValue(RESPONSES[FALLBACK_LOCALE], key)
}
