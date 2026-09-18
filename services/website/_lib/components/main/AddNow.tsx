import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import Link from "next/link";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faDiscord } from "@fortawesome/free-brands-svg-icons";

export default function AddNow({ lang }: { lang: MainPageLangJson["invite"] }) {
    return (
        <div className="flex flex-col gap-8 h-[50vh]">
            <p className="text-6xl font-bold title">
                {lang.title}
            </p>
            <div className="flex items-center justify-center gap-0">
                <Link href={`add.fm01.bot`} className="mt-8 primary-button w-fit text-3xl font-bold py-4 px-8 rounded-2xl">
                    <FontAwesomeIcon icon={faDiscord} /> <span className="font-bold">{lang.subtext}</span>
                </Link>
            </div>
        </div>
    );
}