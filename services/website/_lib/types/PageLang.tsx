import { MainPageLangJson } from "./MainPageLang"
import { TeamPageLangJson } from "./TeamPageLang"
import { StatusPageLangJson } from "./StatusPageLang"
import { PremiumPageLangJson } from "./PremiumPageLang"

export interface WebLangJson {
    header: HeaderLangJson,
    footer: FooterLangJson,
    notFound: NotFoundLangJson,
    main: MainPageLangJson,
    team: TeamPageLangJson,
    status: StatusPageLangJson,
    premium: PremiumPageLangJson,
    "bot-locale": Record<string, unknown>
}

export interface HeaderLangJson {
    premium: string,
    docs: string,
    status: string,
    features: string,
    dashboard: string
}

export interface FooterLangJson {
    contact: {
        title: string,
        discord: string
    },
    links: {
        title: string,
        tos: string,
        privacy: string,
        cookies: string,
        github: string,
        providers: string,
    },
    special: {
        title: string,
        dev: string,
        host: string
    },
    status?: string,
    copyright: string,
    affiliate: string,
}

export interface NotFoundLangJson {
    title: string,
    description: string,
    home: string
}