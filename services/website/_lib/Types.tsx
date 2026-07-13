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

interface HeroType {
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

interface TeamType {
    title: string,
    hiring: string
}

interface AboutType {
    title: string,
    subtext: string,
    tutorial: (string | string[])[]
}

interface FeaturesType {
    title: string,
    subtext: string
}

interface StatusType {
    title: string,
}