import { EmbedType } from "./EmbedLang"

export enum ButtonColors {
    PRIMARY,
    SECONDARY,
    DANGER,
    SUCCESS
}

export interface MessageType {
    message: string,
    username: string,
    avatar: string,
    embeds?: EmbedType[],
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