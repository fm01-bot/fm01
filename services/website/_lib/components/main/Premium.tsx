import Link from "next/link";
import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import { faAdd, faCircleCheck, faCoins, faMailBulk } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";

export default function Premium({ lang }: { lang: MainPageLangJson["premium"] }) {
    const FREE = lang.tiers.free;
    const PREMIUM = lang.tiers.premium;
    const CUSTOM = lang.tiers.custom;
    return (
        <div id="features" className="h-fit">
            <p className="title">
                {lang.title}
            </p>
            <p className="subtext">
                {lang.subtext}
            </p>
            <div className="flex flex-row flex-wrap w-full items-center justify-center gap-4">
                <div id="FREE" className="tier-cards">
                    <div className="inner-container">
                        <span className="tier-title">
                            {FREE.name}
                        </span>
                        <span className="tier-price">
                            {FREE.price}
                        </span>
                        <div className="flex flex-col features">
                            {
                                FREE.features.map((a, i) => (
                                    <span key={i}>
                                        <FontAwesomeIcon icon={faCircleCheck} className="w-6! h-3.5!" />
                                        {a}
                                    </span>
                                ))
                            }
                        </div>
                    </div>
                    <Link href={"https://add.fm01.bot"} className="button">
                        <FontAwesomeIcon icon={faAdd} /> {FREE.button}
                    </Link>
                </div>
                <div id="PREMIUM" className="tier-cards">
                    <div className="inner-container">
                        <span className="tier-title">
                            {PREMIUM.name}
                        </span>
                        <span className="tier-price">
                            {PREMIUM.price}
                        </span>
                        <div className="flex flex-col features">
                            {
                                PREMIUM.features.map((a, i) => (
                                    <span key={i}>
                                        <FontAwesomeIcon icon={faCircleCheck} className="w-6! h-3.5!" />
                                        {a}
                                    </span>
                                ))
                            }
                        </div>
                    </div>
                    <Link href={"https://add.fm01.bot"} className="button">
                        <FontAwesomeIcon icon={faCoins} /> {PREMIUM.button}
                    </Link>
                </div>
                <div id="CUSTOM" className="tier-cards">
                    <div className="inner-container">
                        <span className="tier-title">
                            {CUSTOM.name}
                        </span>
                        <span className="tier-price">
                            {CUSTOM.price}
                        </span>
                        <div className="flex flex-col">
                            {
                                CUSTOM.features.map((a, i) => (
                                    <span key={i}>
                                        <FontAwesomeIcon icon={faCircleCheck} className="w-6! h-3.5!" />
                                        {a}
                                    </span>
                                ))
                            }
                        </div>
                    </div>
                    <Link href={"https://add.fm01.bot"} className="button">
                        <FontAwesomeIcon icon={faMailBulk} /> {CUSTOM.button}
                    </Link>
                </div>
            </div>
            <p className="text-center text-text/50 text-xl mt-8">{lang.disclosure}<Link href={`https://github.com/fm01-bot`} className="link">GitHub</Link>.</p>
        </div >
    );
}