import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import Container from "./showcase/Container";

export default function Features({ lang }: { lang: MainPageLangJson["features"] }) {
    return (
        <div id="features" className="h-fit">
            <p className="title">
                {lang.title}
            </p>
            <p className="subtext">
                {lang.subtext}
            </p>
            <Container lang={lang.container} />
        </div>
    );
}