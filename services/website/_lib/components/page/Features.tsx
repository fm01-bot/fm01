import { FeaturesType } from "@/_lib/Types";
import Container from "../showcase/Container";

export default function Features({ lang }: { lang: FeaturesType }) {
    return (
        <div id="features" className="h-screen">
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