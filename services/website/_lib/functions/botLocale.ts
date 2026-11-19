import { randomInt } from 'node:crypto'
import type { MessageType, ValueSpec } from '@/_lib/types/MessageLang'
import { getResponse } from './botResponses'
import { payloadToMessage } from './responseExtractor'

/**
 * Resolves showcase messages that reference a real bot response.
 *
 * A message with `"botResponse": "mod.warn.response"` is replaced by that response from the
 * bot's locale files (English if the key is missing in the page's language). Its
 * `{placeholders}` are filled from:
 *   1. the closest preceding user command (`?!warn @rnxm 1w Hacking threats`), then
 *   2. the message's `values`, which win over the command.
 */

type Values = Record<string, string>

function replacePlaceholders(value: string, values: Values): string {
    return value.replace(/\{([^{}]+)\}/g, (placeholder, key: string) => values[key] ?? placeholder)
}

function replaceNestedPlaceholders(value: unknown, values: Values): unknown {
    if (typeof value === 'string') return replacePlaceholders(value, values)
    if (Array.isArray(value)) return value.map((item) => replaceNestedPlaceholders(item, values))
    if (typeof value !== 'object' || value === null) return value

    return Object.fromEntries(
        Object.entries(value).map(([key, nestedValue]) => [key, replaceNestedPlaceholders(nestedValue, values)])
    )
}

/** Placeholder values implied by a user command, so the reply matches what was typed. */
function parseCommand(message: string | undefined, author: { name: string, avatar: string } | undefined): Values {
    const command = message?.match(/^\s*\?!([^\s]+)(?:\s+(.+))?$/)
    const values: Values = {}
    if (author) {
        values['author.name'] = author.name
        values['author.avatar'] = author.avatar
        values['author.mention'] = `@${author.name}`
    }
    if (!command) return values

    const name = command[1].toLowerCase()
    const args = command[2]?.trim().split(/\s+/) ?? []

    if (name === 'warn') {
        // ?!warn <user> <length> <reason…>
        if (args[0]) values['warn.user.mention'] = args[0]
        if (args[1]) values['warn.length'] = values['warn.date'] = args[1]
        if (args.length > 2) values['warn.reason'] = args.slice(2).join(' ')
    }
    if (name === 'giveaway') {
        // ?!giveaway <length> <winners> <prize…>
        if (args[0]) values['giveaway.ends'] = values['giveaway.ends.relative'] = args[0]
        if (args[1]) values['giveaway.winners'] = args[1]
        if (args.length > 2) values['giveaway.prize'] = args.slice(2).join(' ')
    }
    return values
}

/**
 * Turns a message's `values` into strings. Plain strings and random numbers resolve first;
 * `botText`/`botList` then pull bot texts and fill their own placeholders with everything
 * known so far (e.g. `work.random` entries use `{amount}`).
 */
function resolveValues(locale: string, specs: Record<string, ValueSpec>, known: Values): Values {
    const values: Values = {}
    const texts: [string, { botText: string } | { botList: string }][] = []

    for (const [key, spec] of Object.entries(specs)) {
        if (typeof spec === 'string') values[key] = spec
        else if ('randomInt' in spec) {
            const [min, max] = spec.randomInt
            values[key] = `${spec.prefix ?? ''}${randomInt(min, max + 1)}`
        } else texts.push([key, spec])
    }

    for (const [key, spec] of texts) {
        const isList = 'botList' in spec
        const ref = isList ? spec.botList : spec.botText
        const found = getResponse(locale, ref)
        const text = isList
            ? (Array.isArray(found) && found.length ? found[randomInt(0, found.length)] : undefined)
            : found
        if (typeof text !== 'string') {
            console.warn(`[botLocale] ${locale}: value "${key}" points at "${ref}", which isn't a ${isList ? 'list of texts' : 'text'}`)
            continue
        }
        values[key] = replacePlaceholders(text, { ...known, ...values })
    }
    return values
}

/** Returns a copy of `messages` with every `botResponse` reference replaced by the bot's reply. */
export function resolveMessages(locale: string, messages: MessageType[]): MessageType[] {
    return messages.map((message, index) => {
        if (!message.botResponse) return message
        const { botResponse, values: specs, ...rest } = message

        const previous = messages.slice(0, index).reverse().find((m) => !m.bot && m.message)
        const known = parseCommand(previous?.message, previous && { name: previous.username, avatar: previous.avatar })
        const values = { ...known, ...resolveValues(locale, specs ?? {}, known) }

        const parts = payloadToMessage(replaceNestedPlaceholders(structuredClone(getResponse(locale, botResponse)), values))
        if (!parts) {
            console.warn(`[botLocale] ${locale}: bot response "${botResponse}" not found or not renderable`)
            return rest
        }
        // Empty values (e.g. `{requirements}`) can leave dangling blank lines.
        for (const embed of parts.embeds) if (embed.description) embed.description = embed.description.trim()

        return {
            ...rest,
            message: parts.content ?? rest.message ?? '',
            embeds: parts.embeds.length ? parts.embeds : undefined,
        }
    })
}
