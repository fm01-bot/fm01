import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import Link from "next/link";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faDiscord } from "@fortawesome/free-brands-svg-icons";

export default function Hero({ lang }: { lang: MainPageLangJson["hero"] }) {
    return (
        <div className="flex flex-col gap-8">
            <div className="flex flex-col items-center w-full">
                <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%]">{lang.title[0]}</h1>
                <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%] text-primary">{lang.title[1]}</h1>
                <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%]">{lang.title[2]}</h1>
            </div>
            <div className=" text-lg md:text-3xl flex flex-col items-center w-full">
                <p className="secondary-text">{lang.subtext[0]}</p>
                <p className="secondary-text">{lang.subtext[1]}</p>
            </div>
            <div className="flex flex-row justify-center items-center gap-5 w-full">
                <Link href={`https://dashboard.fm01.bot/`} className="accent-button flex flex-row gap-2 items-center text-white">
                    <FontAwesomeIcon icon={faDiscord} className="w-7.25! h-7.25!" />
                    <span className="text-2xl font-extrabold leading-[normal]">
                        {lang.invite_btn}
                    </span>
                </Link>
                <Link href={`https://dc.fm01.bot/`} className="accent-secondary-button">
                    <span className="text-2xl leading-[normal]">
                        {lang.support_btn}
                    </span>
                </Link>
            </div>
        </div>
    );
}