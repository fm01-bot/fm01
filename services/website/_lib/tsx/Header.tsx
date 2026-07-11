"use client"
import Link from "next/link";
import { usePathname } from 'next/navigation'
import { motion } from 'framer-motion';
import { useState } from "react";
import Logo from "../svg/Logo";
import Dashboard from "../svg/Dashboard";
import { HeaderJson } from "@lib/Types"



export default function Header({ lang }: { lang: HeaderJson }) {
    const page = usePathname();

    const NAV_LINKS = [
        { href: "/#home", label: lang.home },
        { href: "/#about", label: lang.about },
        { href: "/#features", label: lang.features },
        { href: "/#status", label: lang.status },
        { href: "/#pricing", label: lang.pricing },
    ];

    const [showMenus, setShowMenus] = useState(false);

    return (
        <div className="w-full flex items-center justify-center py-5 px-5">
            <div className="w-275 flex items-center justify-between relative">
                <Link href="/">
                    <Logo width={50} height={50} />
                </Link>

                <div className="hidden items-center justify-between gap-13 relative md:flex">
                    {NAV_LINKS.map((link) => {
                        const isActive = page === link.href;

                        return (
                            <Link
                                key={link.href}
                                href={link.href}
                                className={`relative pb-1 ${isActive ? "text-primary" : ""}`}
                            >
                                {link.label}

                                {isActive && (
                                    <motion.span
                                        layoutId="active-indicator"
                                        className="absolute left-0 -bottom-1 h-1 w-full bg-primary rounded-full"
                                        transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                                    />
                                )}
                            </Link>
                        );
                    })}
                </div>

                <div className="flex flex-row gap-3 items-center justify-center">
                    <Link href="https://dash.fm01.bot" className="flex primary-button text-base p-2! flex-row items-center justify-center gap-1 md:py-2.5! md:px-5!">
                        <Dashboard width={20} height={20} className="w-5 h-5 md:w-3.75 md:h-3.75" /> <p className="hidden md:block">{lang.dashboard}</p>
                    </Link>
                    <div className="block md:hidden z-2">
                        <label
                            className="relative block w-7.5 h-5 cursor-pointer"
                            htmlFor="burger"
                        >
                            <input
                                type="checkbox"
                                id="burger"
                                className="peer hidden"
                                checked={showMenus}
                                onChange={(e) => setShowMenus(e.target.checked)}
                            />


                            {/* Top line */}
                            <span
                                className="absolute left-0 top-0 block h-0.75 w-full rounded-full bg-text transition-all duration-300 ease-in-out 
                            peer-checked:top-1/2 peer-checked:-translate-y-1/2 peer-checked:rotate-45"
                            ></span>

                            {/* Middle line */}
                            <span
                                className="absolute left-0 top-1/2 block h-0.75 w-full -translate-y-1/2 rounded-full bg-text transition-all duration-300 ease-in-out 
                   peer-checked:opacity-0 peer-checked:scale-0"
                            ></span>

                            {/* Bottom line */}
                            <span
                                className="absolute left-0 bottom-0 block h-0.75 w-full rounded-full bg-text transition-all duration-300 ease-in-out 
                            peer-checked:bottom-1/2 peer-checked:translate-y-1/2 peer-checked:-rotate-45"
                            ></span>
                        </label>
                    </div>
                </div>
                <div className={`${showMenus ? "opacity-50" : "opacity-0 scale-[1.5] pointer-events-none z-1 "} duration-300 right-0 block transition-all bottom-0 z-0 fixed w-screen h-screen bg-background blur-3xl`}>
                </div>
                <div className={`${showMenus ? "opacity-100" : "opacity-0 scale-[1.5] pointer-events-none z-2"} duration-300 right-0 flex transition-all bottom-0 z-1 fixed w-screen h-screen items-center justify-center flex-col gap-3 backdrop-blur-md`}>
                    <Logo width={45} height={45} className="mb-4" />

                    {NAV_LINKS.map((link) => {
                        const isActive = page === link.href;

                        return (
                            <Link
                                key={link.href}
                                href={link.href}
                                className={` text-2xl relative pb-1 ${isActive ? "text-primary" : ""}`}
                                onClick={() => { setShowMenus(false) }}
                            >
                                {link.label}
                                {isActive && (
                                    <motion.span
                                        layoutId="active-indicator-2"
                                        className="absolute left-0 -bottom-1 h-1 w-full bg-primary rounded-full"
                                        transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                                    />
                                )}
                            </Link>
                        );
                    })}
                </div>
            </div>
        </div>
    )
}