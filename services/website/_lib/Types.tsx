export interface HeaderJson {
    home: string,
    about: string,
    features: string,
    status: string,
    team: string,
    dashboard: string
}

export interface FooterJson {
    contact: {
        title: string,
        discord: string
    },
    docs: {
        title: string,
        tos: string,
        privacy: string,
        cookies: string
    },
    copyright: string,
    designer: string,
    service: string
}

export interface PageJson {
    hero: HeroType,
    about: AboutType,
    features: FeaturesType,
    status: StatusType,
    team: TeamType
}

export interface HeroType {
    title: string[],
    subtext: string[]
    invite_btn: string,
    support_btn: string
    commands: CommandType[]
}

interface CommandType {
    name: string,
    params: string,
    description: string
}

export interface TeamType {
    title: string,
    hiring: string
}

export interface AboutType {
    title: string,
    subtext: string,
    tutorial: (string | string[])[]
}

export interface FeaturesType {
    title: string,
    subtext: string,
    container: ContainerType
}

export interface StatusType {
    title: string,
}

export enum ButtonColors {
    PRIMARY,
    SECONDARY,
    DANGER,
    SUCCESS
}

export interface ContainerType {
    channels?: ChannelType[]
}

export interface ChannelType {
    title: string,
    description: string,
    messages?: MessageType[]
}

export interface MessageType {
    message: string,
    username: string,
    avatar: string,
    embeds?: EmbedType[],
    buttons?: [
        [ButtonType?, ButtonType?, ButtonType?],
        [ButtonType?, ButtonType?, ButtonType?],
        [ButtonType?, ButtonType?, ButtonType?],
    ]
}

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

export interface FieldType {
    name: string,
    value: string,
    inline?: boolean
}