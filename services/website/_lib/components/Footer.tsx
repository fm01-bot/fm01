"use client"

import Link from "next/link";

import { FooterLangJson } from "@/_lib/types/PageLang"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faDesktop, faLink, faMoon, faSun } from "@fortawesome/free-solid-svg-icons";
import { useTheme } from "@teispace/next-themes";
import { faDiscord, faGithub, faInstagram, faYoutube } from "@fortawesome/free-brands-svg-icons";
import Logo from "../svg/Logo";

export default function Footer({ lang }: { lang: FooterLangJson }) {

    const { theme, setTheme } = useTheme()
    const currentYear = new Date().getFullYear();




    const LINK_LANG: Record<string, string> = {
        "https://github.fm01.bot": lang.links.github,
        "https://support.fm01.bot": "FAQ",
        "https://discord.fm01.bot": "Support server",
        "/pricing": "Pricing",
        "/features": "Features"
    }
    const LINKS = [
        "https://github.fm01.bot",
        "https://support.fm01.bot",
        "https://discord.fm01.bot",
        "/pricing",
        "/features"
    ]
    const SPECIAL_LANG: Record<string, string> = {
        "https://yoursit.ee/adam": `${lang.special.dev} Ace`,
        "https://playdev.hu": `${lang.special.host} PlayClan`
    }

    const SPECIAL_KEY = [
        "https://yoursit.ee/adam",
        "https://playdev.hu"
    ]

    const LEGAL_KEY = [
        "/legal/providers",
        "ignore1",
        "/legal/bot/tos",
        "/legal/bot/privacy",
        "ignore2",
        "/legal/web/tos",
        "/legal/web/privacy",
        "/legal/web/cookies",
    ]

    const LEGAL_LANG: Record<string, string> = {
        "/legal/providers": "Providers",
        "ignore1": "Discord bot",
        "/legal/bot/tos": "Terms of Service",
        "/legal/bot/privacy": "Privacy Policy",
        "ignore2": "Website",
        "/legal/web/tos": "Terms of Service",
        "/legal/web/privacy": "Privacy Policy",
        "/legal/web/cookies": "Cookie Policy"
    }

    const FOOTER_LINKS = [
        {
            "title": lang.links.title,
            "keys": LINKS,
            "lang": LINK_LANG,
            "names": null
        },
        {
            "title": "Legal",
            "keys": LEGAL_KEY,
            "lang": LEGAL_LANG
        },
        {
            "title": lang.special.title,
            "keys": SPECIAL_KEY,
            "lang": SPECIAL_LANG
        },
    ]

    return (
        <div className="footer">
            <div className="container">
                <div className="links">
                    <div>
                        <div className="brand">
                            <Logo width={32} height={32} fill="fill-primary" />
                            <span>fm01</span>
                        </div>
                        <p>Erdei Olivér Márton E.V.</p>
                        <p>Budapest, Perényi Zsigmond u. 25, 1047</p>
                        <Link href={`mailto:support@fm01.bot`} className="link">support@fm01.bot</Link>
                    </div>
                    {
                        FOOTER_LINKS.map((e, i) => {
                            return (
                                <div key={i}>
                                    <h1>{e.title.toUpperCase()}</h1>
                                    <ul>
                                        {
                                            e.keys.map((f, j) => {
                                                if (f.match('ignore')) {
                                                    return (
                                                        <li key={j} className="ignore">{e.lang[f]}</li>
                                                    )
                                                }
                                                return (
                                                    <li key={j}>
                                                        <Link href={f} className="group">
                                                            <FontAwesomeIcon icon={faLink} />
                                                            <span>
                                                                {e.lang[f]}
                                                            </span>
                                                        </Link>
                                                    </li>
                                                )
                                            })
                                        }
                                    </ul>
                                </div>
                            )
                        })
                    }
                </div>


                <div className="settings">
                    <Link className="status" href={`https://status.fm01.bot`}>

                    </Link>
                    <div className="copyright">
                        <span>
                            fm01 © {currentYear}. {lang.copyright}
                        </span>
                    </div>
                    <div className="other">
                        <div className="theme">
                            <FontAwesomeIcon onClick={() => setTheme('light')} icon={faSun} className={`${theme === "light" ? "active" : ""}`} />
                            <FontAwesomeIcon onClick={() => setTheme('system')} icon={faDesktop} className={`${theme === "system" ? "active" : ""}`} />
                            <FontAwesomeIcon onClick={() => setTheme('dark')} icon={faMoon} className={`${theme === "dark" ? "active" : ""}`} />
                            <span className="circle"></span>
                        </div>
                        <div className="socials">
                            <svg width="0" height="0">
                                <linearGradient id="ig-gradient" x1="0%" y1="100%" x2="100%" y2="0%">
                                    <stop stopColor="#fcb045" offset="0%" />
                                    <stop stopColor="#fd1d1d" offset="50%" />
                                    <stop stopColor="#833ab4" offset="100%" />
                                </linearGradient>
                            </svg>
                            <Link href={`https://github.fm01.bot`} target="_blank">
                                <FontAwesomeIcon icon={faGithub} />
                            </Link>
                            <Link href={`https://discord.fm01.bot`} target="_blank">
                                <FontAwesomeIcon icon={faDiscord} />
                            </Link>
                            <Link href={`https://youtube.fm01.bot`} target="_blank">
                                <FontAwesomeIcon icon={faYoutube} />
                            </Link>
                            <Link href={`https://insta.fm01.bot`} target="_blank">
                                <FontAwesomeIcon icon={faInstagram} />
                            </Link>
                            <Link href={`https://yoursitee.fm01.bot`} target="_blank">

                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}