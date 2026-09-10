import { notFound } from 'next/navigation'
import { getDictionary, hasLocale } from './dictionaries'
import Hero from "@/_lib/components/main/Hero"
import Features from "@/_lib/components/main/Features"
import PromotedServers from "@/_lib/components/main/PromotedServers"
import Premium from '@/_lib/components/main/Premium'

type PageProps = {
    params: Promise<{ lang: string }>;
};


export default async function Page({ params }: PageProps) {
    const { lang } = await params;

    if (!hasLocale(lang)) notFound();

    const dict = await getDictionary(lang);

    const translation = dict.main;

    return (
        <div className="w-full flex items-center justify-center max-w-screen">
            <div className="w-280 max-w-screen flex flex-col gap-49 p-2 laptop:p-0 mt-66">

                <div className="absolute w-screen h-screen top-0 left-0 grid-bg -z-1">

                </div>

                <Hero lang={translation.hero} />

                <PromotedServers lang={translation.servers} />

                <Features lang={translation.features} />

                <Premium lang={translation.premium} />
            </div>
        </div>
    )
}