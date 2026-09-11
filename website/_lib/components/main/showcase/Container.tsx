"use client"
import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import Channel from "./Channel";
import { useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faChevronDown } from "@fortawesome/free-solid-svg-icons";

export default function Container({ lang }: { lang?: MainPageLangJson["features"]["container"] }) {

    const [active, setActive] = useState(0);

    if (!lang || !lang.channels) {
        return (<></>);
    }

    return (
        <div className="flex flex-row h-125 w-full rounded-lg overflow-hidden">
            <div className="dark:bg-[#09080b]/50 bg-text/10 w-67 max-w-[50%] rounded-bl-lg p-4">
                <span className=" text-xl text-text/50">fm01 <FontAwesomeIcon icon={faChevronDown} className="w-3.75! h-3.75!" /></span>
                <div className="flex flex-col items-start w-full gap-0.5 mt-2">
                    {
                        lang?.channels?.map((c, i) => {
                            return (
                                <span
                                    onClick={() => { setActive(i) }}
                                    key={`cl-${i}`}
                                    className={`text-text/50 h-8 flex items-center justify-start gap-2 py-1 px-2 hover:bg-text/20 hover:text-text rounded-lg w-full ${active == i ? "bg-text/20! text-text!" : ""}`}>
                                    <span className="text-xl leading-0 font-semibold">#</span>
                                    <span className="leading-0">{c.title}</span>
                                </span>
                            )
                        })
                    }
                </div>
            </div>
            <div className="bg-text/3 w-full flex flex-col h-full relative">
                <span className="w-full flex items-center justify-start gap-1 py-2 border-b border-b-text/30 px-3 shrink-0">
                    <span className="text-xl text-text/50">#</span>
                    {lang.channels[active].title}
                    <span className="text-[#09080b]/30 text-sm px-1">●</span>
                    <span className="text-text/50">{lang.channels[active].description}</span>
                </span>
                <div className="flex-1 overflow-y-scroll p-2 flex items-end">
                    {
                        lang?.channels?.map((c, i) => {
                            return (
                                <div key={`c-${i}`} className={"" + (active == i ? "opacity-100 relative max-h-full" : "opacity-0 mt-30 fixed pointer-events-none")}>
                                    <Channel key={`c-${i}`} {...c} />
                                </div>
                            )
                        })
                    }
                </div>

                <div className=" p-3 py-2 w-full">
                    <div className="border border-text/30 bg-[#09080b]/10 py-3 px-4 w-full rounded-lg text-text/50">You do not have permission to send messages in this channel.</div>
                </div>
            </div>
        </div>
    )
}