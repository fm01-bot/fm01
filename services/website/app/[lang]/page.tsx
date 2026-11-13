import { notFound } from 'next/navigation'
import { getDictionary, hasLocale } from './dictionaries'
import Hero from "@/_lib/components/main/Hero"
import Features from "@/_lib/components/main/Features"
import PromotedServers from "@/_lib/components/main/PromotedServers"
import Premium from '@/_lib/components/main/Premium'
import AddNow from '@/_lib/components/main/AddNow'
import { MainPageLangJson } from '@/_lib/types/MainPageLang'
import { MessageType } from '@/_lib/types/MessageLang'
import type { Metadata } from 'next'
import { pageMetadata } from '@/_lib/functions/metadata'
import { resolveMessages } from '@/_lib/functions/botLocale'

type Dictionary = Awaited<ReturnType<typeof getDictionary>>

type PageProps = {
    params: Promise<{ lang: string }>;
};


export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
    const { lang } = await params;
    if (!hasLocale(lang)) return {};

    const hero = (await getDictionary(lang)).main.hero;
    return pageMetadata({
        lang,
        path: '',
        title: hero.title.join(' '),
        description: hero.subtext.join(' '),
    });
}

export default async function Page({ params }: PageProps) {
    const { lang } = await params;

    if (!hasLocale(lang)) notFound();

    const dict = await getDictionary(lang);

    function parseLang(dictionary: Dictionary): Dictionary {
        const resolvedDictionary = structuredClone(dictionary)

        for (const channel of resolvedDictionary.main.features.container.channels ?? []) {
            channel.messages = resolveMessages(
                resolvedDictionary,
                (channel.messages ?? []) as MessageType[],
                channel.title,
            ) as typeof channel.messages
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