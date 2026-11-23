
const dictionaries = {
    en: () => import('@shared/localization/website/en.json').then((module) => module.default),
    hu: () => import('@shared/localization/website/hu.json').then((module) => module.default),
}

export const languages = ['hu', 'en'];

export type Locale = keyof typeof dictionaries

export const hasLocale = (locale: string): locale is Locale =>
    Object.hasOwn(dictionaries, locale)

export const getDictionary = async (locale: Locale) => dictionaries[locale]()