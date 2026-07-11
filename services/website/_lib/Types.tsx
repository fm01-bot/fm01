export interface HeaderJson {
    home: string,
    about: string,
    features: string,
    status: string,
    pricing: string,
    dashboard: string
}

export interface MainPageType {
    hero: HeroType,
}

export interface HeroType {
    title: string[],
    subtext: string[]
    invite_btn: string,
    support_btn: string
    commands: CommandType[]
}

export interface CommandType {
    name: string,
    params: string,
    description: string
}