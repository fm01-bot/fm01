import 'server-only'

const dictionaries = {
    en: () => import('@lib/translations/en.json').then((module) => module.default),
    hu: () => import('@lib/translations/hu.json').then((module) => module.default),
}

export type Locale = keyof typeof dictionaries

export const hasLocale = (locale: string): locale is Locale =>
    locale in dictionaries

export const getDictionary = async (locale: Locale) => dictionaries[locale]()