import { MainPageLangJson } from "./MainPageLang"
import { TeamPageLangJson } from "./TeamPageLang"
import { StatusPageLangJson } from "./StatusPageLang"
import { PremiumPageLangJson } from "./PremiumPageLang"

export interface WebLangJson {
    header: HeaderLangJson,
    footer: FooterLangJson,
    main: MainPageLangJson,
    team: TeamPageLangJson,
    status: StatusPageLangJson,
    premium: PremiumPageLangJson
}

export interface HeaderLangJson {
    premium: string,
    docs: string,
    status: string,
    team: string,
    dashboard: string
}

export interface FooterLangJson {
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