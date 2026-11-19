import { ButtonColors, type ButtonType } from '../types/MessageLang'
import type { EmbedType } from '../types/EmbedLang'

/**
 * Turns a bot response from `shared/localization/responses/<lang>.l10n.json` into what a
 * showcase message renders: classic embeds stay embeds, Components V2 become one embed.
 */

type JsonObject = Record<string, unknown>

const isObject = (value: unknown): value is JsonObject =>
    typeof value === 'object' && value !== null && !Array.isArray(value)

function getPath(value: unknown, path: string[]): unknown {
    return path.reduce<unknown>((current, key) => (isObject(current) ? current[key] : undefined), value)
}

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

/** A bot response turned into what a showcase message renders. */
export interface MessageParts {
    content?: string
    embeds: EmbedType[]
}

/**
 * Converts a whole bot response into showcase parts: its `content`, every classic embed, and
 * Components V2 (rendered as one embed). A bare array is treated as an `embeds` list, since
 * some bot keys (e.g. `work.embeds`) hold only the embeds.
 */
export function payloadToMessage(payload: unknown): MessageParts | undefined {
    const object = Array.isArray(payload) ? { embeds: payload } : payload
    if (!isObject(object)) return undefined

    const embeds = (Array.isArray(object.embeds) ? object.embeds.filter(isObject) : []).map(normaliseEmbed)
    const components = Array.isArray(object.components) ? object.components : []
    if (components.length) {
        const fromComponents = componentsToEmbed(components)
        // Classic messages keep their buttons in action rows next to the embeds.
        if (embeds.length) {
            if (fromComponents.buttons?.length) embeds.at(-1)!.buttons ??= fromComponents.buttons
        } else {
            embeds.push(fromComponents)
        }
    }

    const content = typeof object.content === 'string' ? object.content : undefined
    if (!content && !embeds.length) return undefined
    return { content, embeds }
}
