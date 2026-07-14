import ThemeToggle from "@/_lib/components/ThemeToggle"
import { PageJson } from "@lib/Types"
import { notFound } from 'next/navigation'
import { getDictionary, hasLocale } from './dictionaries'
import Hero from "@/_lib/components/page/Hero"
import About from "@/_lib/components/page/About"
import Features from "@/_lib/components/page/Features"
import Status from "@/_lib/components/page/Status"
import Team from "@/_lib/components/page/Team"

type PageProps = {
    params: Promise<{ lang: string }>;
};


export default async function Page({ params }: PageProps) {
    const { lang } = await params;

    if (!hasLocale(lang)) notFound();

    const dict = await getDictionary(lang);

    const translation: PageJson = dict.main;

    return (
        <div className="w-full flex items-center justify-center max-w-screen">
            <div className="w-280 max-w-screen flex flex-col gap-49 p-2 md:p-0">
                <div className="h-22.5">
                    <br />
                    <br />
                    <br />
                    <br />
                </div>

                { /* Hero section */}
                <Hero lang={translation.hero} />

                <About lang={translation.about} />

                <Features lang={translation.features} />

                <Status lang={translation.status} />

                <Team lang={translation.team} />

                <ThemeToggle />
            </div>
        </div>
    )
}