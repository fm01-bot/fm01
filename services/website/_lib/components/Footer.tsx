import Link from "next/link";

import { FooterLangJson } from "@/_lib/types/PageLang"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faLink } from "@fortawesome/free-solid-svg-icons";

export default function Footer({ lang }: { lang: FooterLangJson }) {
    const currentYear = new Date().getFullYear();
    const LINK_LANG = {
        "https://fm01.bot/tos": lang.links.tos,
        "https://fm01.bot/privacy": lang.links.privacy,
        "https://fm01.bot/cookies": lang.links.cookies,
        "https://github.fm01.bot": lang.links.github,
        "https://fm01.bot/providers": lang.links.providers
    }
    const LINKS: (keyof typeof LINK_LANG)[] = [
        "https://fm01.bot/tos",
        "https://fm01.bot/privacy",
        "https://fm01.bot/cookies",
        "https://github.fm01.bot",
        "https://fm01.bot/providers"
    ]
    const SPECIAL_LANG = {
        "https://yoursit.ee/adam": lang.special.dev,
        "https://playdev.hu": lang.special.host
    }

    const SPECIAL_NAME = {
        "https://yoursit.ee/adam": "Ace",
        "https://playdev.hu": "PlayClan"
    }

    const SPECIAL_KEY: (keyof typeof SPECIAL_LANG)[] = [
        "https://yoursit.ee/adam",
        "https://playdev.hu"
    ]

    return (
        <div className="w-full flex items-center justify-center pb-5 px-5 flex-col py-10 md:pt-20 bg-text/7 laptop:[clip-path:polygon(0_0,100%_10%,100%_100%,0_100%)] pt-15">
            <div className="w-full max-w-280 flex flex-col laptop:flex-row items-start laptop:flex-wrap laptop:justify-around relative flex-wrap gap-10">
                <div>
                    <h1 className="pb-2">{lang.contact.title}</h1>
                    <p>Erdei Olivér Márton E.V.</p>
                    <p>Budapest, Perényi Zsigmond u. 25, 1047</p>
                    <Link href={`mailto:support@fm01.bot`} className="link">support@fm01.bot</Link>
                    <br />
                    <Link className="link" href={`https://dc.fm01.bot/`}>{lang.contact.discord}</Link>
                </div>

                <div>
                    <h1 className="pb-2">{lang.links.title}</h1>
                    <div className="flex flex-col">
                        {
                            LINKS.map((e, i) => {
                                return (
                                    <Link className="hover:text-primary hover:cursor-pointer" href={e} key={i} >{LINK_LANG[e]}<FontAwesomeIcon className="text-primary ml-1" icon={faLink} /></Link>
                                )
                            })
                        }
                    </div>
                </div>
                <div>
                    <h1 className="pb-2">{lang.special.title}</h1>
                    <div className="flex flex-col">
                        {
                            SPECIAL_KEY.map((e, i) => {
                                return (
                                    <span key={i}>{SPECIAL_LANG[e]} <Link className="hover:text-primary hover:cursor-pointer hover:font-light" href={e} >{SPECIAL_NAME[e]}<FontAwesomeIcon className="text-primary ml-1" icon={faLink} /></Link></span>
                                )
                            })
                        }
                    </div>
                </div>
            </div>
            <div className="w-full max-w-275 flex laptop:items-center flex-col justify-around text-sm pt-5 flex-wrap">
                <span>
                    fm01 © {currentYear}. {lang.copyright}
                </span>
                <span className="text-text/50">{lang.affiliate}</span>
            </div>
        </div>
    )
}