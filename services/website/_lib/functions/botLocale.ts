import { randomInt } from 'node:crypto'
import type { EmbedType } from '@/_lib/types/EmbedLang'
import type { MessageType } from '@/_lib/types/MessageLang'

/**
 * Resolves embed references in showcase messages.
 *
 * A message's `embeds` may hold strings such as `"bot-locale.warn.embed"`: a path into the
 * language JSON, pointing at the embed the real bot sends. The embed is looked up, and its
 * `{placeholders}` are filled from the closest preceding user command (`?!warn @rnxm 1w …`),
 * falling back to showcase defaults.
 */

type PlaceholderValues = Record<string, string>

const showcaseDefaults: Record<string, PlaceholderValues> = {
    warn: {
        "warn.user.mention": "@rnxm",
        "warn.reason": "Hacking threats",
        "warn.length": "1w",
        "warn.date": "1w",
    },
    giveaway: giveawayValues("Nitro Classic Giveaway", "1", "2 days"),
}

/** Older bot locales use `{prize}`, newer ones `{giveaway.prize}`; fill both. */
function giveawayValues(prize: string, winners: string, ends: string, host = "@fm01"): PlaceholderValues {
    return {
        prize,
        winners,
        ends,
        "giveaway.prize": prize,
        "giveaway.winners": winners,
        "giveaway.ends": ends,
        "giveaway.ends.relative": `in ${ends}`,
        "author.mention": host,
        requirements: "",
    }
}

export function getPathValue(value: unknown, reference: string): unknown {
    return reference.split('.').reduce<unknown>((current, key) => {
        if (typeof current !== 'object' || current === null) return undefined
        return (current as Record<string, unknown>)[key]
    }, value)
}

function randomInteger(min: number, max: number): string {
    return String(randomInt(min, max + 1))
}

function replacePlaceholders(value: string, values: PlaceholderValues): string {
    return value.replace(/\{([^{}]+)\}/g, (placeholder, key: string) => values[key] ?? placeholder)
}

function replaceNestedPlaceholders(value: unknown, values: PlaceholderValues): unknown {
    if (typeof value === 'string') return replacePlaceholders(value, values)
    if (Array.isArray(value)) return value.map((item) => replaceNestedPlaceholders(item, values))
    if (typeof value !== 'object' || value === null) return value

    return Object.fromEntries(
        Object.entries(value).map(([key, nestedValue]) => [
            key,
            replaceNestedPlaceholders(nestedValue, values),
        ])
    )
}

function parseCommand(message: string | undefined, author: { name: string, avatar: string } | undefined): { module?: string, values: PlaceholderValues } {
    const command = message?.match(/^\s*\?!([^\s]+)(?:\s+(.+))?$/)
    const values: PlaceholderValues = {}

    if (!command) return { values }

    const commandName = command[1].toLowerCase()
    const argumentsText = command[2]?.trim() ?? ''
    const argumentsList = argumentsText ? argumentsText.split(/\s+/) : []

    if (commandName === 'warn') {
        const reason = argumentsList.slice(2).join(' ')
        values['warn.user.mention'] = argumentsList[0] ?? showcaseDefaults.warn['warn.user.mention']
        values['warn.length'] = argumentsList[1] ?? showcaseDefaults.warn['warn.length']
        values['warn.date'] = values['warn.length']
        values['warn.reason'] = reason || showcaseDefaults.warn['warn.reason']
    }
    if (commandName === 'play') {
        values['author.name'] = author?.name ?? "Pearoo"
        values['author.avatar'] = author?.avatar ?? "/images/pearoo.png"
        values['track.author'] = "Rick Astley"
        values['track.duration'] = "3:34"
        values['track.title'] = "Never Gonna Give You Up"
        values['track.url'] = "https://www.youtube.com/watch?v=iNTeY4hFwNU"
    }
    if (commandName == 'giveaway') {
        const defaults = showcaseDefaults.giveaway
        Object.assign(values, giveawayValues(
            argumentsList.slice(2).join(' ') || defaults.prize,
            argumentsList[1] ?? defaults.winners,
            argumentsList[0] ?? defaults.ends,
            author ? `@${author.name}` : undefined,
        ))
    }

    return { module: commandName, values }
}

function getModuleFromReference(reference: string): string | undefined {
    return reference.match(/^bot-locale\.([^.]+)\./)?.[1]
}

function getBotEmbed(dictionary: unknown, module: string): unknown {
    const embed = getPathValue(dictionary, `bot-locale.${module}.embed`)
    if (embed && typeof embed === 'object' && !Array.isArray(embed)) return embed

    const embeds = getPathValue(dictionary, `bot-locale.${module}.embeds`)
    return Array.isArray(embeds) ? embeds[0] : undefined
}

/**
 * Returns a copy of `messages` with every embed reference replaced by the resolved embed.
 * `fallbackModule` names the bot-locale module used when neither the reference nor a
 * preceding command says which one applies (the home page passes the channel title).
 */
export function resolveMessages(dictionary: unknown, messages: MessageType[], fallbackModule?: string): MessageType[] {
    return messages.map((message, messageIndex) => {
        if (!message.embeds?.length) return message

        const previousMessage = messages
            .slice(0, messageIndex)
            .reverse()
            .find((candidate) => !candidate.bot && candidate.message)
        const author = previousMessage ? {
            name: previousMessage.username,
            avatar: previousMessage.avatar
        } : undefined
        const command = parseCommand(previousMessage?.message, author)

        const embeds = message.embeds.map((embed) => {
            const referenceModule = typeof embed === 'string'
                ? getModuleFromReference(embed)
                : undefined
            const localeModule = referenceModule ?? command.module ?? fallbackModule
            const resolvedEmbed = typeof embed === 'string'
                ? getPathValue(dictionary, embed)
                : embed
            const fallbackEmbed = localeModule ? getBotEmbed(dictionary, localeModule) : undefined
            const sourceEmbed = resolvedEmbed && typeof resolvedEmbed === 'object'
                ? resolvedEmbed
                : fallbackEmbed

            if (!sourceEmbed || typeof sourceEmbed !== 'object' || Array.isArray(sourceEmbed)) {
                return embed
            }

            const values: PlaceholderValues = {
                ...(localeModule ? showcaseDefaults[localeModule] ?? {} : {}),
                ...command.values,
            }

            if (localeModule === 'work') {
                const randomEntries = getPathValue(dictionary, 'bot-locale.work.random')
                const randomText = Array.isArray(randomEntries) && randomEntries.length > 0
                    ? randomEntries[randomInt(0, randomEntries.length)]
                    : undefined
                values.amount = randomInteger(50, 500)
                values.random = typeof randomText === 'string'
                    ? replacePlaceholders(randomText, values)
                    : ''
            }

            if (localeModule === 'giveaway') {
                values.participants = randomInteger(111, 999)
                values['giveaway.entries'] = values.participants
            }
            if (localeModule === 'warn') values['warn.id'] = `#${randomInteger(1111, 9999)}`

            const resolved = replaceNestedPlaceholders(structuredClone(sourceEmbed), values) as EmbedType
            // Empty placeholders (e.g. `{requirements}`) can leave dangling blank lines.
            if (resolved.description) resolved.description = resolved.description.trim()
            return resolved
        })

        return { ...message, embeds }
    })
}
