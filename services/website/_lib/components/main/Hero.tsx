import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import Link from "next/link";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faDiscord } from "@fortawesome/free-brands-svg-icons";

export default function Hero({ lang }: { lang: MainPageLangJson["hero"] }) {
    return (
        <div className="flex flex-col gap-8">
            <div className="flex flex-col laptop:flex-row gap-5 items-center justify-center w-full">
                <h1 className="font-extrabold! text-5xl! laptop:text-8xl! leading-[85%]">{lang.title[0]}</h1>
                <h1 className="font-extrabold! text-5xl! laptop:text-8xl! leading-[85%] text-primary">{lang.title[1]}</h1>
                <h1 className="font-extrabold! text-5xl! laptop:text-8xl! leading-[85%]">{lang.title[2]}</h1>
            </div>
            <div className=" flex flex-col items-center w-full">
                <p className="secondary-text">{lang.subtext[0]}</p>
                <p className="secondary-text">{lang.subtext[1]}</p>
            </div>
            <div className="flex flex-row justify-center items-center gap-2.5 laptop:gap-5 w-full">
                <Link href={`https://dashboard.fm01.bot/`} className="accent-button flex flex-row gap-1 laptop:gap-2 items-center text-white">
                    <FontAwesomeIcon icon={faDiscord} className="laptop:w-7.25! laptop:h-7.25! w-5! h-5! p-0.5" />
                    <span className="text-base laptop:text-2xl font-extrabold leading-[normal]">
                        {lang.invite_btn}
                    </span>
                </Link>
                <Link href={`https://dc.fm01.bot/`} className="btn-sec">
                    <span className="text-base font-normal laptop:text-2xl leading-[normal]">
                        {lang.support_btn}
                    </span>
                </Link>
            </div>
        </div>
    );
}