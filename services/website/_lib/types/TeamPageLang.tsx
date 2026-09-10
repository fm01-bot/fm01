export interface TeamPageLangJson {
    hero: HeroLangJson
    members: MemberLangJson
}

interface HeroLangJson {
    title: string[]
}

interface MemberLangJson {
    name: string,
    alias: string,
    aliases: string[],
    role: string,
    connect: {
        steam?: string,
        github?: string,
        twitch?: string,
        instagram?: string,
        twitter?: string,
        youtube?: string,
        yoursitee?: string
    },
    introduction: string, // markdown string, we need a parser
}