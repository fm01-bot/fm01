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

    function parseLang(dictionary: Dictionary): Dictionary {
        const resolvedDictionary = structuredClone(dictionary)
        const channels = resolvedDictionary.main.features.container.channels ?? []

        for (const channel of channels) {
            for (const message of channel.messages ?? []) {
                const typedMessage = message as MessageType
                typedMessage.embeds = typedMessage.embeds?.map((embed) => {
                    if (typeof embed !== 'string') return embed

                    const resolvedEmbed = getPathValue(resolvedDictionary, embed)
                    return resolvedEmbed && typeof resolvedEmbed === 'object'
                        ? resolvedEmbed as EmbedType
                        : embed
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