"use client"
import Link from "next/link";
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

    const [isScrolled, setIsScrolled] = useState(false);

    useEffect(() => {
        const scrollCheck = () => setIsScrolled(window.scrollY > 10);
        scrollCheck();
        window.addEventListener('scroll', scrollCheck, { passive: true });
        window.addEventListener('resize', scrollCheck);

        return () => {
            window.removeEventListener('scroll', scrollCheck);
            window.removeEventListener('resize', scrollCheck);
        };
    }, [NAV_LINKS]);

    return (
        <header className={`navbar ${isScrolled ? "bg-text/5 backdrop-blur-xs" : ""}`}>
            <div className="navbar-inner">
                <Link href="/" className="brand">
                    <Logo width={30} height={30} fill={'fill-primary'} />
                    <span>fm01</span>
                </Link>

                <nav className="nav-links-container">
                    <div className={`nav-links ${isScrolled ? "bg-contrast" : "bg-text/5"}`}>
                        {NAV_LINKS.map((l, i) => (
                            <Link key={i} href={l.href}>
                                {l.label}
                            </Link>
                        ))}
                    </div>
                </nav>

                <div className="actions">
                    {/* Desktop Theme Toggle */}
                    <div className="theme">
                        {theme === "system" ? (
                            <FontAwesomeIcon icon={faDesktop} onClick={() => setTheme('light')} className="cursor-pointer" />
                        ) : theme === "light" ? (
                            <FontAwesomeIcon icon={faSun} onClick={() => setTheme('dark')} className="cursor-pointer" />
                        ) : (
                            <FontAwesomeIcon icon={faMoon} onClick={() => setTheme('system')} className="cursor-pointer" />
                        )}
                    </div>

                    {/* Desktop Lang Select */}
                    <select className="lang-select" defaultValue={code} onChange={(e) => router.replace(`${e.target.value}/${page}`)}>
                        {languages.map((l, i) => (
                            <option key={i} value={l}>{l.toLocaleUpperCase()}</option>
                        ))}
                    </select>

                    {/* Desktop Dashboard Button */}
                    <Link href="https://dash.fm01.bot" className="dashboard-btn">
                        <Dashboard width={14} height={14} fill="fill-white" />
                        <span>Dashboard</span>
                    </Link>

                    {/* Mobile Menu Wrapper */}
                    <div className="mobile-menu">
                        <input type="checkbox" id="burger" />
                        <label className="burger" htmlFor="burger">
                            <span></span>
                            <span></span>
                            <span></span>
                        </label>

                        <div className="overlay">
                            <div className="overlay-links">
                                {NAV_LINKS.map((l, i) => (
                                    <Link key={i} href={l.href} className="overlay-link">
                                        <span>{l.label}</span>
                                    </Link>
                                ))}
                            </div>
                            <div className="flex flex-row gap-4">
                                <div className="overlay-theme">
                                    {theme === "system" ? (
                                        <FontAwesomeIcon icon={faDesktop} onClick={() => setTheme('light')} className="cursor-pointer" />
                                    ) : theme === "light" ? (
                                        <FontAwesomeIcon icon={faSun} onClick={() => setTheme('dark')} className="cursor-pointer" />
                                    ) : (
                                        <FontAwesomeIcon icon={faMoon} onClick={() => setTheme('system')} className="cursor-pointer" />
                                    )}
                                </div>

                                <select className="lang-select" defaultValue={code} onChange={(e) => router.replace(`${e.target.value}/${page}`)}>
                                    {languages.map((l, i) => (
                                        <option key={i} value={l}>{l.toLocaleUpperCase()}</option>
                                    ))}
                                </select>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </header>
    )
}