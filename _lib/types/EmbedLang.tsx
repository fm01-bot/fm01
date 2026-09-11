import { ButtonType } from "./MessageLang"

export interface EmbedType {
    title?: string,
    description?: string,
    url?: string,
    color?: string,
    fields?: FieldType[],
    footer?: {
        text?: string,
        icon_url?: string
    },
    image?: {
        url: string
    },
    thumbnail?: {
        url: string
    },
    author?: {
        name: string,
        url?: string,
        icon_url?: string
    },
    buttons?: ButtonType[][]
}

export interface FieldType {
    name: string,
    value: string,
    inline?: boolean
}