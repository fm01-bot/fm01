import { HeroType } from "@/_lib/Types";
import CommandScroller from "../CommandScroller";
import Link from "next/link";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faPlus } from "@fortawesome/free-solid-svg-icons";

export default function Hero({ lang }: { lang: HeroType }) {
    return (
        <div id="home">
            <div className="flex items-center justify-around relative z-0">
                <div className="w-xl gap-14.5 flex items-start flex-col">
                    <div className="flex flex-col items-center md:items-start w-full">
                        <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%]">{lang.title[0]}</h1>
                        <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%] text-primary">{lang.title[1]}</h1>
                        <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%]">{lang.title[2]}</h1>
                    </div>
                    <div className=" text-lg md:text-3xl flex flex-col items-center md:items-start w-full">
                        <p className="secondary-text">{lang.subtext[0]}</p>
                        <p className="secondary-text">{lang.subtext[1]}</p>
                    </div>
                    <div className="flex flex-row justify-center md:justify-start gap-5 w-full">
                        <Link href={`https://dashboard.fm01.bot/`} className="primary-button flex flex-row gap-2"> <FontAwesomeIcon icon={faPlus} width={15} /> {lang.invite_btn}</Link>
                        <Link href={`https://dc.fm01.bot/`} className="secondary-button">{lang.support_btn}</Link>
                    </div>
                </div>

                <div className="w-xl hidden min-[880px]:block">
                    <CommandScroller />
                </div>
            </div>
        </div>
    );
}