import Logo from "@/_lib/svg/Logo";
import { AboutType } from "@/_lib/types/PageLang";

export default function About({ lang }: { lang: AboutType }) {

    const steps = [
        {
            child: (
                <span className="flex items-center">
                    {lang.tutorial[0][0]}
                    <span className="mx-1.5 px-1 leading-6 pb-[0.1rem] flex items-center justify-center rounded-[0.3rem] border border-blue-400 bg-background text-[1.3rem]">
                        /
                    </span>
                    {lang.tutorial[0][1]}
                </span>
            )
        },
        {
            child: lang.tutorial[1]
        },
        {
            child: lang.tutorial[2]
        }
    ]

    return (
        <div id="about" className="h-fit max-w-screen flex flex-col items-center justify-center">
            <p className="title">{lang.title}</p>
            <p className="subtext">{lang.subtext}</p>
            <div className="flex mt-8 gap-8 flex-row items-center justify-center flex-wrap max-w-full">
                <div className="flex w-136 max-w-full flex-col gap-4">

                    {
                        steps.map((e, i) => {
                            return (
                                <div key={i} className="flex p-2 md:p-0 items-center rounded-2xl border border-text/10 hover:border-text hover:opacity-100 opacity-65 bg-text/10 transition-all">
                                    <div className=" w-fit mx-2 md:mx-6 text-center text-xl md:text-6xl md:py-3 font-bold">
                                        {i + 1}
                                    </div>
                                    <div className="flex w-full items-center justify-center text-base md:text-2xl font-medium md:pr-8">
                                        {e.child}
                                    </div>
                                </div>
                            )
                        })
                    }

                </div>

                <div className="flex h-74 w-136 max-w-full flex-col gap-4 rounded-3xl bg-[#1e1e21] p-2 font-sans">

                    {/* Top Panel - Placeholder Area */}
                    <div className="flex h-72 w-full overflow-hidden rounded-2xl border border-[#36363a]">

                        {/* Left Sidebar */}
                        <div className="flex p-2 shrink-0 items-center justify-center bg-[#141416]">
                            <Logo width={22.875} height={22.875} />
                        </div>

                        {/* Main Content Area */}
                        <div className="flex flex-1 items-center justify-center bg-[#252529] px-8 text-center">
                            <p className="text-[1.25rem] font-normal leading-snug text-white">
                                this is just a placeholder for now<br />
                                assets will be created later :)
                            </p>
                        </div>
                    </div>

                    {/* Bottom Panel - Action Bar */}
                    <div className="flex h-18 w-full items-center gap-6 rounded-2xl border border-[#36363a] bg-[#212124] px-2 py-4">

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
                                className="h-8 w-8"
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
    );
}