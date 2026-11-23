import { EmbedType } from "./EmbedLang"

export enum ButtonColors {
    PRIMARY,
    SECONDARY,
    DANGER,
    SUCCESS
}

/**
 * How a placeholder in a referenced bot response is filled:
 * a fixed string, another bot text, a random entry of a bot list, or a random number.
 */
export type ValueSpec =
    | string
    | { botText: string }
    | { botList: string }
    | { randomInt: [number, number], prefix?: string }

export interface MessageType {
    message?: string,
    username: string,
    avatar: string,
    embeds?: EmbedType[],
    /** Exact key of a bot response in shared/localization/responses, e.g. "mod.warn.response". */
    botResponse?: string,
    /** Placeholder values for `botResponse`; they win over values parsed from the preceding command. */
    values?: Record<string, ValueSpec>,
    bot?: boolean,
    buttons?: [
        [ButtonType?, ButtonType?, ButtonType?],
        [ButtonType?, ButtonType?, ButtonType?],
        [ButtonType?, ButtonType?, ButtonType?],
    ]
}

export interface ButtonType {
    label: string,
    url?: string,
    emoji?: string,
    color?: ButtonColors,
    disabled?: boolean
}