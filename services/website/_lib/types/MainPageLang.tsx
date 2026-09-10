import { MessageType } from "./MessageLang"

export interface MainPageLangJson {
    hero: HeroLangJson,
    servers: ServersLangJson,
    features: FeaturesLangJson,
    premium: PremiumLangJson,
    invite: InviteLangJson,
}

export interface PromotedServersJson {
    name: string,
    count: number
    icon: string,
    invite: string
}

interface ServersLangJson {
    title: string,
    subtext: string[],
    memberstext: string,
    invitetext: string[],
}

interface HeroLangJson {
    title: string[],
    subtext: string[]
    invite_btn: string,
    support_btn: string
}

interface FeaturesLangJson {
    title: string,
    subtext: string,
    container: ContainerType
}

interface PremiumLangJson {
    title: string,
    subtext: string,
    tiers: {
        free: {
            name: string,
            features: [],
            price: string,
            button: string,
            recommend: string,
        },
        premium: {
            name: string,
            features: []
            price: string,
            button: string,
            recommend: string,
        },
        custom: {
            name: string,
            features: []
            price: string,
            button: string,
            recommend: string,
        }
    },
    disclosure: string
}

interface InviteLangJson {
    title: string,
    subtext: string
}

interface ContainerType {
    channels?: ChannelType[]
}

export interface ChannelType {
    title: string,
    description: string,
    messages?: MessageType[]
}