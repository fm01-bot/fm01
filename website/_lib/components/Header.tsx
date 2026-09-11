"use client"
import Link from "next/link";
import { motion } from 'framer-motion';
import { useState, useEffect, useMemo } from "react";
import Logo from "../svg/Logo";
import Dashboard from "../svg/Dashboard";
import { WebLangJson } from "@/_lib/types/PageLang"
import { usePathname, useRouter } from "next/navigation";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faDesktop, faMoon, faSun } from "@fortawesome/free-solid-svg-icons";
import { languages } from "@/app/[lang]/dictionaries";
import { useTheme } from "@teispace/next-themes";

export default function Header({ lang, code }: { lang: WebLangJson["header"], code: string }) {

    const page = usePathname().substring(3);

    const router = useRouter();

    const { theme, setTheme } = useTheme()


    const NAV_LINKS = useMemo(
        () => [
            { href: "/team", label: lang.team },
            { href: "/status", label: lang.status },
            { href: "https://docs.fm01.bot", label: lang.docs },
            { href: "/premium", label: lang.premium }
        ], [lang]
    )

    const [showMenus, setShowMenus] = useState(false); // Variable used for displaying menu in mobile view


    const [isScrolled, setIsScrolled] = useState(false); // Variable to set navbar background if user scrolled

    useEffect(() => {
        const scrollCheck = () => {
            setIsScrolled(window.scrollY > 10);
        };

        scrollCheck();
        window.addEventListener('scroll', scrollCheck, { passive: true });
        window.addEventListener('resize', scrollCheck);

        return () => {
            window.removeEventListener('scroll', scrollCheck);
            window.removeEventListener('resize', scrollCheck);
        };
    }, [NAV_LINKS]);

    return (
        <div className={`w-full max-w-screen fixed top-0 left-0 z-10 flex items-center justify-center`}>
            <div className="w-280 max-w-full self-stretch flex flex-row items-center justify-between! relative navbar py-4">
                <Link href="/" className="flex flex-row items-center gap-1 self-stretch">
                    <Logo width={30} height={30} fill={'fill-primary'} />
                    <span className="text-3xl text-primary font-black ">fm01</span>
                </Link>
                <div className={`nav-links-container`}>
                    <div className={`nav-links self-stretch pointer-events-auto ${isScrolled ? "bg-contrast" : "bg-text/5"}`}>
                        {
                            NAV_LINKS.map((l, i) => {
                                return (
                                    <Link key={i} href={l.href}>
                                        {l.label}
                                    </Link>
                                )
                            })
                        }
                    </div>
                </div>
                <div className="self-stretch flex flex-row items-center gap-0!">
                    <div className="flex flex-row items-center gap-6! p-4">
                        {
                            theme == "system" ? (
                                <FontAwesomeIcon icon={faDesktop} onClick={() => {
                                    setTheme('light')
                                }} />
                            ) : theme == "light" ? (
                                <FontAwesomeIcon icon={faSun} onClick={() => {
                                    setTheme('dark')
                                }} />
                            ) : (
                                <FontAwesomeIcon icon={faMoon} onClick={() => {
                                    setTheme('system')
                                }} />
                            )
                        }
                        <div>
                            <select className="lang-select gap-0 text-text!" style={{ lineHeight: "normal" }} defaultValue={code} onChange={(e) => {
                                router.replace(`${e.target.value}/${page}`)
                            }}>
                                {
                                    languages.map((l, i) => {
                                        return (
                                            <option key={i} value={l}>{l.toLocaleUpperCase()}</option>
                                        )
                                    })
                                }
                            </select>
                        </div>
                    </div>
                    <Link href={`https://dash.fm01.bot`} className=" p-4 py-2.5 rounded-2xl bg-primary gap-2 flex flex-row items-center text-white">
                        <Dashboard width={14} height={14} fill="fill-white" />
                        <span style={{ lineHeight: "normal" }} >Dashboard</span>
                    </Link>
                </div>
            </div>
        </div>
    )
}