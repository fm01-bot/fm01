import ThemeToggle from "@/_lib/tsx/ThemeToggle"
import Link from "next/link"
import CommandScroller from "@/_lib/tsx/CommandScroller"
import Logo from "@/_lib/svg/Logo"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { faPlus } from "@fortawesome/free-solid-svg-icons"
import { MainPageType } from "@lib/Types"


export default function Page({ lang }: { lang: MainPageType }) {
    return (<>
        <div className=" h-[40vh] flex items-center justify-around">
            <div className="w-xl gap-14.5 flex items-start flex-col">
                <div className="flex flex-col items-center md:items-start gap-[-20px]">
                    <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%]">{lang.hero.title[0]}</h1>
                    <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%] text-primary">{lang.hero.title[1]}</h1>
                    <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%]">{lang.hero.title[2]}</h1>
                </div>
                <div className=" text-lg md:text-3xl flex flex-col items-center md:items-start w-full">
                    <p className="secondary-text">{lang.hero.subtext[0]}</p>
                    <p className="secondary-text">{lang.hero.subtext[1]}</p>
                </div>
                <div className="flex flex-row justify-center md:justify-start gap-5 w-full">
                    <Link href={`https://dashboard.fm01.bot/`} className="primary-button flex flex-row gap-2"> <FontAwesomeIcon icon={faPlus} width={15} /> {lang.hero.invite_btn}</Link>
                    <Link href={`https://dc.fm01.bot/`} className="secondary-button">{lang.hero.support_btn}</Link>
                </div>
            </div>

            <div className="w-xl hidden min-[880px]:block">
                <CommandScroller />
            </div>
        </div>



        <ThemeToggle />
    </>)
}