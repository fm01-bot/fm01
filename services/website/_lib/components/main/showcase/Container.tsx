"use client"
import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import Channel from "./Channel";
import { useRef, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faArrowLeft, faChevronDown } from "@fortawesome/free-solid-svg-icons";

export default function Container({ lang }: { lang?: MainPageLangJson["features"]["container"] }) {

    const [active, setActive] = useState(0);
    const [channelsOpen, setChannelsOpen] = useState(false);
    const touchStartX = useRef<number | null>(null);

    if (!lang || !lang.channels) {
        return (<></>);
    }

    const handleTouchStart = (event: React.TouchEvent<HTMLDivElement>) => {
        touchStartX.current = event.touches[0]?.clientX ?? null;
    };

    const handleTouchEnd = (event: React.TouchEvent<HTMLDivElement>) => {
        if (touchStartX.current === null) {
            return;
        }

        const touchEndX = event.changedTouches[0]?.clientX;
        if (touchEndX === undefined) {
            touchStartX.current = null;
            return;
        }

        const swipeDistance = touchEndX - touchStartX.current;
        if (swipeDistance > 70) {
            setChannelsOpen(true);
        } else if (swipeDistance < -70) {
            setChannelsOpen(false);
        }

        touchStartX.current = null;
    };

    return (
        <div
            className={`showcase-container ${channelsOpen ? "channels-open" : ""}`}
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
        >
            <div className="channels">
                <span className="server-title">fm01 <FontAwesomeIcon icon={faChevronDown} className="w-3.75! h-3.75!" /></span>
                <div className="channel-list">
                    {
                        lang?.channels?.map((c, i) => {
                            return (
                                <span
                                    onClick={() => { setActive(i); console.log(i) }}
                                    key={`cl-${i}`}
                                    className={`channel-name ${active == i ? "bg-text/20! text-text!" : ""}`}>
                                    <span>#</span>
                                    <span>{c.title}</span>
                                </span>
                            )
                        })
                    }
                </div>
            </div>
            {channelsOpen && (
                <button
                    className="channels-backdrop"
                    type="button"
                    aria-label="Close channel list"
                    onClick={() => setChannelsOpen(false)}
                />
            )}
            <div className="channel-container">
                <div className="channel-title">
                    <button
                        className="channel-back"
                        type="button"
                        aria-label="Show channel list"
                        onClick={() => setChannelsOpen(true)}
                    >
                        <FontAwesomeIcon icon={faArrowLeft} />
                    </button>
                    <span>#</span>
                    <span>{lang.channels[active].title}</span>
                    <span>•</span>
                    <span>{lang.channels[active].description}</span>
                </div>
                <div className="channel-content">
                    {
                        lang?.channels?.map((c, i) => {
                            return (
                                <div key={`c-${i}`} className={active == i ? "opacity-100 relative max-h-full" : "opacity-0 mt-30 fixed pointer-events-none"}>
                                    <Channel key={`c-${i}`} {...c} />
                                </div>
                            )
                        })
                    }
                </div>

                <div className="text-area">
                    <div>{lang.noperms}</div>
                </div>
            </div>
        </div>
    )
}