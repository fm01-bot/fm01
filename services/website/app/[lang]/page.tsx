import { notFound } from 'next/navigation'
import { getDictionary, hasLocale } from './dictionaries'
import Hero from "@/_lib/components/main/Hero"
import Features from "@/_lib/components/main/Features"
import PromotedServers from "@/_lib/components/main/PromotedServers"
import Premium from '@/_lib/components/main/Premium'
import AddNow from '@/_lib/components/main/AddNow'
import { EmbedType } from '@/_lib/types/EmbedLang'
import { MainPageLangJson } from '@/_lib/types/MainPageLang'
import { MessageType } from '@/_lib/types/MessageLang'
import { randomInt } from 'node:crypto'

type Dictionary = Awaited<ReturnType<typeof getDictionary>>

type PageProps = {
    params: Promise<{ lang: string }>;
};


export default async function Page({ params }: PageProps) {
    const { lang } = await params;

    if (!hasLocale(lang)) notFound();

    const dict = await getDictionary(lang);

    function getPathValue(value: unknown, reference: string): unknown {
        return reference.split('.').reduce<unknown>((current, key) => {
            if (typeof current !== 'object' || current === null) return undefined
            return (current as Record<string, unknown>)[key]
        }, value)
    }

    type PlaceholderValues = Record<string, string>

    const showcaseDefaults: Record<string, PlaceholderValues> = {
        warn: {
            "warn.user.mention": "@rnxm",
            "warn.reason": "Hacking threats",
            "warn.length": "1w",
            "warn.date": "1w",
        },
        giveaway: {
            prize: "Nitro Classic Giveaway",
            winners: "1",
            ends: "2 days",
        },
    }

    function randomInteger(min: number, max: number): string {
        return String(randomInt(min, max + 1))
    }

    function replacePlaceholders(value: string, values: PlaceholderValues): string {
        return value.replace(/\{([^{}]+)\}/g, (placeholder, key: string) => values[key] ?? placeholder)
    }

    function replaceNestedPlaceholders(value: unknown, values: PlaceholderValues): unknown {
        if (typeof value === 'string') return replacePlaceholders(value, values)
        if (Array.isArray(value)) return value.map((item) => replaceNestedPlaceholders(item, values))
        if (typeof value !== 'object' || value === null) return value

        return Object.fromEntries(
            Object.entries(value).map(([key, nestedValue]) => [
                key,
                replaceNestedPlaceholders(nestedValue, values),
            ])
        )
    }

    function parseCommand(message: string | undefined, author: { name: string, avatar: string } | undefined): { module?: string, values: PlaceholderValues } {
        const command = message?.match(/^\s*\?!([^\s]+)(?:\s+(.+))?$/)
        const values: PlaceholderValues = {}

        if (!command) return { values }

        const commandName = command[1].toLowerCase()
        const argumentsText = command[2]?.trim() ?? ''
        const argumentsList = argumentsText ? argumentsText.split(/\s+/) : []

        if (commandName === 'warn') {
            const reason = argumentsList.slice(2).join(' ')
            values['warn.user.mention'] = argumentsList[0] ?? showcaseDefaults.warn['warn.user.mention']
            values['warn.length'] = argumentsList[1] ?? showcaseDefaults.warn['warn.length']
            values['warn.date'] = values['warn.length']
            values['warn.reason'] = reason || showcaseDefaults.warn['warn.reason']
        }
        if (commandName === 'play') {
            values['author.name'] = author?.name ?? "Pearoo"
            values['author.avatar'] = author?.avatar ?? "/images/pearoo.png"
            values['track.author'] = "Rick Ashley"
            values['track.duration'] = "3:34"
            values['track.title'] = "Never Gonna Give You Up"
            values['track.url'] = "https://www.youtube.com/watch?v=iNTeY4hFwNU"
        }
        if (commandName == 'giveaway') {
            const prize = argumentsList.slice(2).join(' ')
            values['prize'] = prize
            values['winners'] = argumentsList[1]
            values['ends'] = argumentsList[0]
        }

        return { module: commandName, values }
    }

    function getModuleFromReference(reference: string): string | undefined {
        return reference.match(/^bot-locale\.([^.]+)\./)?.[1]
    }

    function getBotEmbed(dictionary: Dictionary, module: string): unknown {
        const embed = getPathValue(dictionary, `bot-locale.${module}.embed`)
        if (embed && typeof embed === 'object' && !Array.isArray(embed)) return embed

        const embeds = getPathValue(dictionary, `bot-locale.${module}.embeds`)
        return Array.isArray(embeds) ? embeds[0] : undefined
    }

    function parseLang(dictionary: Dictionary): Dictionary {
        const resolvedDictionary = structuredClone(dictionary)
        const channels = resolvedDictionary.main.features.container.channels ?? []

        for (const channel of channels) {
            const messages = channel.messages ?? []

            for (const [messageIndex, message] of messages.entries()) {
                const typedMessage = message as MessageType
                const previousMessage = [...messages]
                    .slice(0, messageIndex)
                    .reverse()
                    .find((candidate) => !candidate.bot && candidate.message)
                const author = previousMessage ? {
                    name: previousMessage.username,
                    avatar: previousMessage.avatar
                } : undefined
                const command = parseCommand(previousMessage?.message, author)

                typedMessage.embeds = typedMessage.embeds?.map((embed) => {
                    const referenceModule = typeof embed === 'string'
                        ? getModuleFromReference(embed)
                        : undefined
                    const localeModule = referenceModule ?? command.module ?? channel.title
                    const resolvedEmbed = typeof embed === 'string'
                        ? getPathValue(resolvedDictionary, embed)
                        : embed
                    const fallbackEmbed = getBotEmbed(resolvedDictionary, localeModule)
                    const sourceEmbed = resolvedEmbed && typeof resolvedEmbed === 'object'
                        ? resolvedEmbed
                        : fallbackEmbed

                    if (!sourceEmbed || typeof sourceEmbed !== 'object' || Array.isArray(sourceEmbed)) {
                        return embed
                    }

                    const values: PlaceholderValues = {
                        ...(showcaseDefaults[localeModule] ?? {}),
                        ...command.values,
                    }

                    if (localeModule === 'work') {
                        const randomEntries = getPathValue(resolvedDictionary, 'bot-locale.work.random')
                        const randomText = Array.isArray(randomEntries) && randomEntries.length > 0
                            ? randomEntries[randomInt(0, randomEntries.length)]
                            : undefined
                        values.amount = randomInteger(50, 500)
                        values.random = typeof randomText === 'string'
                            ? replacePlaceholders(randomText, values)
                            : ''
                    }

                    if (localeModule === 'giveaway') values.participants = randomInteger(111, 999)
                    if (localeModule === 'warn') values['warn.id'] = `#${randomInteger(1111, 9999)}`

                    return replaceNestedPlaceholders(structuredClone(sourceEmbed), values) as EmbedType
                })
            }
        }

        return resolvedDictionary
    }

    const translation = parseLang(dict).main as MainPageLangJson;


    return (
        <div className="w-full flex items-center justify-center max-w-screen">
            <div className="w-280 max-w-screen flex flex-col gap-49 p-3 laptop:p-0 mt-66">

                <div className="absolute w-screen h-screen top-0 left-0 grid-bg -z-1">

                </div>

                <Hero lang={translation.hero} />

                <PromotedServers lang={translation.servers} />

                <Features lang={translation.features} />

                <Premium lang={translation.premium} />

                <AddNow lang={translation.invite} />
            </div>
        </div>
    )
}