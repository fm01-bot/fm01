"use client"
import Link from "next/link";
import { useState, useEffect, useMemo } from "react";
import Logo from "../svg/Logo";
import Dashboard from "../svg/Dashboard";
import { WebLangJson } from "@/_lib/types/PageLang"
import LangSelector from "./LangSelector";

export default function Header({ lang, code }: { lang: WebLangJson["header"], code: string }) {

    const NAV_LINKS = useMemo(
        () => [
            { href: `/features`, label: lang.features },
            { href: `/status`, label: lang.status },
            { href: "https://docs.fm01.bot", label: lang.docs },
            { href: `/premium`, label: lang.premium }
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
        <header className={`navbar ${isScrolled ? " bg-text/5 backdrop-blur-xs laptop:bg-transparent laptop:backdrop-blur-none" : ""}`}>
            <div className="navbar-inner">
                <Link href="/" className="brand">
                    <Logo width={30} height={30} fill={'fill-primary'} />
                    <span>fm01</span>
                </Link>

                <nav className="nav-links-container">
                    <div className={`nav-links`}>
                        {NAV_LINKS.map((l, i) => (
                            <Link key={i} href={l.href} >
                                {l.label}
                            </Link>
                        ))}
                    </div>
                </nav>

                <div className="actions">
                    <div className="langlight">

                        {/* FIX: Replaced 'inset-0' with explicit negative offsets to bleed under the border */}
                        <div className={`absolute hidden laptop:block -top-0.5 -bottom-0.5 -left-0.5 right-0 -z-10 rounded-2xl bg-contrast/30 backdrop-blur-xl pointer-events-none`}></div>

                        {/* 2. Desktop Theme Toggle */}
                        {/* <div className="theme" onClick={() => {
                            console.log("asd");
                            if (theme === "system") setTheme("light");
                            if (theme === "light") setTheme("dark");
                            if (theme === "dark") setTheme("system")
                        }}>
                            <FontAwesomeIcon
                                icon={theme === "system" ? faDesktop : theme === "light" ? faSun : faMoon}
                                className="w-4 h-4 cursor-pointer"
                            />
                        </div> */}

                        {/* 3. Desktop Lang Select */}
                        <div className="hidden laptop:block">
                            <LangSelector currentLangCode={code} />
                        </div>

                        <Link href="https://dash.fm01.bot" className="-my-0.5 dashboard-btn">
                            <Dashboard width={14} height={14} fill="fill-white" />
                            <span>Dashboard</span>
                        </Link>
                    </div>


                    {/* Desktop Dashboard Button */}

                    {/* Mobile Menu Wrapper */}
                    <div className="mobile-menu">
                        <div className="burger-class">
                            <input type="checkbox" id="overlay" />
                            <label className="burger" htmlFor="overlay">
                                <span></span>
                                <span></span>
                                <span></span>
                            </label>
                        </div>

                        <div className="overlay">
                            <div className="overlay-links">
                                {NAV_LINKS.map((l, i) => (
                                    <Link key={i} href={l.href} className="overlay-link">
                                        <span>{l.label}</span>
                                    </Link>
                                ))}
                            </div>
                            <div className="flex flex-row gap-4">
                                <LangSelector currentLangCode={code} />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </header>
    )
}