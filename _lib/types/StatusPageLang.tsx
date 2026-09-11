export interface StatusPageLangJson {
    hero: HeroLangJson,
    shards: ShardsLangJson,
}

interface HeroLangJson {
    title: string[],
}

interface ShardsLangJson {
    title: string,
    subtext: string,

}