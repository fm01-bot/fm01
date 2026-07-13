import ThemeToggle from "@/_lib/tsx/ThemeToggle"
import Link from "next/link"
import CommandScroller from "@/_lib/tsx/CommandScroller"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { faPlus } from "@fortawesome/free-solid-svg-icons"
import { PageJson } from "@lib/Types"
import { notFound } from 'next/navigation'
import { getDictionary, hasLocale } from './dictionaries'
import Logo from "@/_lib/svg/Logo"


export default async function Page({ params }: PageProps<'/[lang]'>) {
    const { lang } = await params

    if (!hasLocale(lang)) notFound()

    const dict = await getDictionary(lang)

    const translation: PageJson = dict.main


    const steps = [
        {
            child: (
                <span className="flex items-center">
                    {translation.about.tutorial[0][0]}
                    <span className="mx-1.5 px-1 leading-[1.5rem] pb-[0.1rem] flex items-center justify-center rounded-[0.3rem] border border-blue-400 bg-background text-[1.3rem]">
                        /
                    </span>
                    {translation.about.tutorial[0][1]}
                </span>
            )
        },
        {
            child: translation.about.tutorial[1]
        },
        {
            child: translation.about.tutorial[2]
        }
    ]
    return (
        <div className="w-full flex items-center justify-center max-w-screen">
            <div className="w-[70rem] max-w-screen flex flex-col gap-49 p-2 md:p-0">
                <div className="h-22.5">
                    <br />
                    <br />
                    <br />
                    <br />
                </div>

                { /* Hero section */}
                <div id="home">
                    <div className="flex items-center justify-around relative z-0">
                        <div className="w-xl gap-14.5 flex items-start flex-col">
                            <div className="flex flex-col items-center md:items-start w-full">
                                <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%]">{translation.hero.title[0]}</h1>
                                <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%] text-primary">{translation.hero.title[1]}</h1>
                                <h1 className="font-extrabold! text-6xl! md:text-8xl! leading-[85%]">{translation.hero.title[2]}</h1>
                            </div>
                            <div className=" text-lg md:text-3xl flex flex-col items-center md:items-start w-full">
                                <p className="secondary-text">{translation.hero.subtext[0]}</p>
                                <p className="secondary-text">{translation.hero.subtext[1]}</p>
                            </div>
                            <div className="flex flex-row justify-center md:justify-start gap-5 w-full">
                                <Link href={`https://dashboard.fm01.bot/`} className="primary-button flex flex-row gap-2"> <FontAwesomeIcon icon={faPlus} width={15} /> {translation.hero.invite_btn}</Link>
                                <Link href={`https://dc.fm01.bot/`} className="secondary-button">{translation.hero.support_btn}</Link>
                            </div>
                        </div>

                        <div className="w-xl hidden min-[880px]:block">
                            <CommandScroller />
                        </div>
                    </div>
                </div>

                <div id="about" className="h-fit max-w-screen flex flex-col items-center justify-center">
                    <p className="title">{translation.about.title}</p>
                    <p className="subtext">{translation.about.subtext}</p>
                    <div className="flex mt-[2rem] gap-[2rem] flex-row items-center justify-center flex-wrap max-w-full">
                        <div className="flex w-[34rem] max-w-full flex-col gap-[1rem]">

                            {
                                steps.map((e, i) => {
                                    return (
                                        <div key={i} className="flex p-2 md:p-0 items-center rounded-[1rem] border border-text/10 hover:border-text hover:opacity-100 opacity-65 bg-text/10 transition-all">
                                            <div className=" w-fit mx-2 md:mx-6 text-center text-xl md:text-6xl md:py-3 font-bold">
                                                {i + 1}
                                            </div>
                                            <div className="flex w-full items-center justify-center text-base md:text-2xl font-medium md:pr-[2rem]">
                                                {e.child}
                                            </div>
                                        </div>
                                    )
                                })
                            }

                        </div>

                        <div className="flex h-[18.5rem] w-[34rem] max-w-full flex-col gap-[1rem] rounded-[1.5rem] bg-[#1e1e21] p-[0.5rem] font-sans">

                            {/* Top Panel - Placeholder Area */}
                            <div className="flex h-[18rem] w-full overflow-hidden rounded-[1rem] border border-[#36363a]">

                                {/* Left Sidebar */}
                                <div className="flex p-[0.5rem] shrink-0 items-center justify-center bg-[#141416]">
                                    <Logo width={22.875} height={22.875} />
                                </div>

                                {/* Main Content Area */}
                                <div className="flex flex-1 items-center justify-center bg-[#252529] px-[2rem] text-center">
                                    <p className="text-[1.25rem] font-normal leading-snug text-white">
                                        this is just a placeholder for now<br />
                                        assets will be created later :)
                                    </p>
                                </div>
                            </div>

                            {/* Bottom Panel - Action Bar */}
                            <div className="flex h-[4.5rem] w-full items-center gap-[1.5rem] rounded-[1rem] border border-[#36363a] bg-[#212124] px-[0.5rem] py-[1rem]">

                                {/* Plus Button */}
                                <button className="flex items-center justify-center text-[#8e8e93] transition-colors hover:text-white">
                                    <svg
                                        width="22.875"
                                        height="22.875"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="1.5"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        className="h-[2rem] w-[2rem]"
                                    >
                                        <line x1="12" y1="5" x2="12" y2="19"></line>
                                        <line x1="5" y1="12" x2="19" y2="12"></line>
                                    </svg>
                                </button>

                                {/* Slash Trigger */}
                                <span className="text-[1.5rem] leading-none mb-[0.3rem] font-medium text-white">
                                    /
                                </span>

                            </div>

                        </div>
                    </div>
                </div>

                <div id="features" className="h-screen">
                    <p className="title">
                        {translation.features.title}
                    </p>
                    <p className="subtext">
                        {translation.features.subtext}
                    </p>
                </div>

                <div id="status" className="h-screen">
                    <p className="title">
                        {translation.status.title}
                    </p>
                </div>

                <div id="team" className="h-screen">
                    <p className="title">
                        {translation.team.title}
                    </p>
                </div>



                <ThemeToggle />
            </div>
        </div>
    )
}