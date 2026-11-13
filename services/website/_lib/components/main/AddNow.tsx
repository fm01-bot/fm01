import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import Link from "next/link";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faDiscord } from "@fortawesome/free-brands-svg-icons";

export default function AddNow({ lang }: { lang: MainPageLangJson["invite"] }) {
    return (
        <div className="flex flex-col h-fit mb-28">
            <p className="title">
                {lang.title}
            </p>
            <div className="flex items-center justify-center gap-0">
                <Link href={`https://add.fm01.bot`} className="mt-8 primary-button flex items-center justify-center gap-2 w-fit text-xl laptop:text-3xl font-bold">
                    <FontAwesomeIcon icon={faDiscord} className="w-8 h-8" /> <span className="font-bold">{lang.subtext}</span>
                </Link>
            </div>
        </div>
    );
}