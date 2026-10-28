import { notFound } from "next/navigation";
import Features from "@/_lib/components/main/Features";
import type { MainPageLangJson } from "@/_lib/types/MainPageLang";
import { getDictionary, hasLocale } from "../dictionaries";

export default async function Page({
    params,
}: {
    params: Promise<{ lang: string }>;
}) {
    const { lang } = await params;

    if (!hasLocale(lang)) {
        notFound();
    }

    const dictionary = await getDictionary(lang);
    return (
        <div className="mt-30">
            <Features lang={dictionary.main.features as MainPageLangJson["features"]} />
        </div>
    );
}
