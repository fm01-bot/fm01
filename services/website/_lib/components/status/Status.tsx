import { StatusPageLangJson } from "@/_lib/types/StatusPageLang";

export default function Status({ lang }: { lang: StatusPageLangJson }) {
    return (
        <div id="status" className="h-screen">
            <p className="title">
                {lang.hero.title.join(" ")}
            </p>
        </div>
    );
}