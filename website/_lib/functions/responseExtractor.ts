import { ButtonColors, type ButtonType } from '../types/MessageLang'
import type { EmbedType } from '../types/EmbedLang'

/**
 * Schema-agnostic extraction of bot responses from the bot's `*.l10n.json` files.
 *
 * The bot repo reorganises its localization files from time to time (e.g. the giveaway
 * message moved from `giveaway.start.response.embeds` to a Components V2 container under
 * `giveaway.layout.active`). Instead of hard-coding paths, we search a module's subtree for
 * every "response payload" (an object with an `embeds` or `components` array), score the
 * candidates using keyword hints, and normalise the winner into the website's `EmbedType`.
 */

type JsonObject = Record<string, unknown>

export interface ResponseTarget {
    /** Dot path of the module subtree, e.g. `"voice.play"`. Located by search if it moved. */
    root: string
    /** Path keywords to prefer, best first (e.g. `["now_playing"]`). */
    prefer?: string[]
    /** Extra path keywords to avoid, on top of the error-like defaults. */
    avoid?: string[]
    /**
     * When the chosen response has no buttons, look for a plain string under a `button` key
     * in the module subtree and attach it as a button (older schemas stored it separately).
     */
    buttonFallback?: boolean
}

interface Candidate {
    path: string[]
    payload: JsonObject
    order: number
}

const DEFAULT_AVOID = [
    'error', 'errors', 'not_found', 'cancelled', 'canceled', 'ended', 'already',
    'already_joined', 'failed', 'invalid', 'missing', 'denied', 'no_permission',
]

const isObject = (value: unknown): value is JsonObject =>
    typeof value === 'object' && value !== null && !Array.isArray(value)

function getPath(value: unknown, path: string[]): unknown {
    return path.reduce<unknown>((current, key) => (isObject(current) ? current[key] : undefined), value)
}

/**
 * Resolves `root` inside `data`. If the exact path is gone, finds the shallowest object whose
 * key is the last segment and whose ancestors contain the other segments in order.
 */
export function findSubtree(data: unknown, root: string): unknown {
    const segments = root.split('.').filter(Boolean)
    const exact = getPath(data, segments)
    if (exact !== undefined) return exact

    const last = segments.at(-1)
    const ancestors = segments.slice(0, -1)
    const queue: { value: unknown, path: string[] }[] = [{ value: data, path: [] }]

    while (queue.length) {
        const { value, path } = queue.shift()!
        if (!isObject(value)) continue
        for (const [key, child] of Object.entries(value)) {
            const childPath = [...path, key]
            if (key === last && containsInOrder(path, ancestors)) return child
            queue.push({ value: child, path: childPath })
        }
    }
    return undefined
}

function containsInOrder(path: string[], wanted: string[]): boolean {
    let index = 0
    for (const key of path) if (key === wanted[index]) index++
    return index === wanted.length
}

/** First value stored under `key` anywhere in `value` (breadth-first) that passes `accept`. */
export function findByKey<T>(value: unknown, key: string, accept: (found: unknown) => found is T): T | undefined {
    const queue: unknown[] = [value]
    while (queue.length) {
        const current = queue.shift()
        if (Array.isArray(current)) { queue.push(...current); continue }
        if (!isObject(current)) continue
        if (key in current && accept(current[key])) return current[key] as T
        queue.push(...Object.values(current))
    }
    return undefined
}

function isResponsePayload(value: JsonObject): boolean {
    const embeds = value.embeds
    const components = value.components
    return (Array.isArray(embeds) && embeds.some(isObject))
        || (Array.isArray(components) && components.some(isObject))
}

function collectCandidates(value: unknown, path: string[] = [], out: Candidate[] = []): Candidate[] {
    if (!isObject(value)) return out
    if (isResponsePayload(value)) out.push({ path, payload: value, order: out.length })
    for (const [key, child] of Object.entries(value)) {
        if (key === 'embeds' || key === 'components') continue
        collectCandidates(child, [...path, key], out)
    }
    return out
}

function score(candidate: Candidate, target: ResponseTarget): number {
    const keys = candidate.path.map((key) => key.toLowerCase())
    const prefer = target.prefer ?? []
    const avoid = [...DEFAULT_AVOID, ...(target.avoid ?? [])]
    let total = 0

    prefer.forEach((word, index) => {
        if (keys.includes(word.toLowerCase())) total += (prefer.length - index) * 10
    })
    for (const word of avoid) if (keys.includes(word.toLowerCase())) total -= 20
    if (candidate.payload.ephemeral === true) total -= 2
    total -= keys.length * 0.1
    return total
}

/* ---------- normalisation into EmbedType ---------- */

const BUTTON_STYLES: Record<string, ButtonColors> = {
    primary: ButtonColors.PRIMARY, '1': ButtonColors.PRIMARY,
    secondary: ButtonColors.SECONDARY, '2': ButtonColors.SECONDARY,
    success: ButtonColors.SUCCESS, '3': ButtonColors.SUCCESS,
    danger: ButtonColors.DANGER, '4': ButtonColors.DANGER,
}

const typeName = (component: JsonObject): string => {
    const type = component.type
    const numeric: Record<number, string> = {
        1: 'action_row', 2: 'button', 9: 'section', 10: 'text_display', 11: 'thumbnail',
        12: 'media_gallery', 14: 'separator', 17: 'container',
    }
    return typeof type === 'number' ? numeric[type] ?? String(type) : String(type ?? '')
}

function toColor(value: unknown): string | undefined {
    if (typeof value === 'number') return `#${value.toString(16).padStart(6, '0')}`
    return typeof value === 'string' ? value : undefined
}

function toButton(component: JsonObject): ButtonType | undefined {
    const emoji = isObject(component.emoji) ? component.emoji.name : component.emoji
    const label = [typeof emoji === 'string' ? emoji : '', typeof component.label === 'string' ? component.label : '']
        .filter(Boolean).join(' ')
    if (!label) return undefined

    const button: ButtonType = { label }
    if (typeof component.url === 'string') button.url = component.url
    else {
        const color = BUTTON_STYLES[String(component.style ?? '').toLowerCase()]
        if (color !== undefined) button.color = color
    }
    if (component.disabled === true) button.disabled = true
    return button
}

function normaliseEmbed(embed: JsonObject): EmbedType {
    const result = structuredClone(embed) as EmbedType & { color?: unknown }
    const color = toColor(embed.color)
    if (color) result.color = color
    else delete result.color
    return result
}

/** Converts a Components V2 tree (containers, text displays, buttons…) into one embed. */
function componentsToEmbed(components: unknown[]): EmbedType {
    const texts: string[] = []
    const buttons: ButtonType[] = []
    const embed: EmbedType = {}

    const walk = (list: unknown[]) => {
        for (const component of list) {
            if (!isObject(component)) continue
            switch (typeName(component)) {
                case 'container':
                    embed.color ??= toColor(component.accent_color)
                    break
                case 'text_display':
                    if (typeof component.content === 'string') texts.push(component.content)
                    break
                case 'button': {
                    const button = toButton(component)
                    if (button) buttons.push(button)
                    break
                }
                case 'thumbnail': {
                    const url = getPath(component, ['media', 'url'])
                    if (typeof url === 'string') embed.thumbnail ??= { url }
                    break
                }
                case 'media_gallery': {
                    const url = Array.isArray(component.items)
                        ? getPath(component.items[0], ['media', 'url'])
                        : undefined
                    if (typeof url === 'string') embed.image ??= { url }
                    break
                }
            }
            if (isObject(component.accessory)) walk([component.accessory])
            if (Array.isArray(component.components)) walk(component.components)
        }
    }
    walk(components)

    const heading = texts[0]?.match(/^#{1,3}\s+(.+)$/)
    if (heading) {
        embed.title = heading[1]
        texts.shift()
    }
    const description = texts.join('\n').trim()
    if (description) embed.description = description
    if (buttons.length) embed.buttons = buttons
    return embed
}

function payloadToEmbed(payload: JsonObject): EmbedType | undefined {
    const embeds = Array.isArray(payload.embeds) ? payload.embeds.filter(isObject) : []
    const components = Array.isArray(payload.components) ? payload.components : []

    if (embeds.length) {
        const embed = normaliseEmbed(embeds[0])
        // Classic messages keep their buttons in action rows next to the embed.
        const extra = componentsToEmbed(components).buttons
        if (extra?.length && !embed.buttons?.length) embed.buttons = extra
        return embed
    }
    if (components.length) return componentsToEmbed(components)
    return undefined
}

/**
 * Finds the best-matching response for `target` in `data` and returns it as an `EmbedType`,
 * or `undefined` when the module holds no renderable response at all.
 */
export function extractResponse(data: unknown, target: ResponseTarget): EmbedType | undefined {
    const subtree = findSubtree(data, target.root)
    const candidates = collectCandidates(subtree)
    if (!candidates.length) return undefined

    const best = candidates
        .map((candidate) => ({ candidate, score: score(candidate, target) }))
        .sort((a, b) => b.score - a.score || a.candidate.order - b.candidate.order)[0].candidate

    const embed = payloadToEmbed(best.payload)
    if (embed && target.buttonFallback && !embed.buttons?.length) {
        const label = findByKey(subtree, 'button', (v): v is string => typeof v === 'string')
        if (label) embed.buttons = [{ label }]
    }
    return embed
}
