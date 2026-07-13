"use client"
import Link from "next/link";
import { motion } from 'framer-motion';
import { useState, useEffect } from "react";
import Logo from "../svg/Logo";
import Dashboard from "../svg/Dashboard";
import { HeaderJson } from "@lib/Types"

export default function Header({ lang }: { lang: HeaderJson }) {
    const NAV_LINKS = [
        { href: "#home", label: lang.home },
        { href: "#about", label: lang.about },
        { href: "#features", label: lang.features },
        { href: "#status", label: lang.status },
        { href: "#team", label: lang.team },
    ];

    const [showMenus, setShowMenus] = useState(false);
    // Track the active section by its href instead of the page URL
    const [activeSection, setActiveSection] = useState(NAV_LINKS[0].href);

    const [isScrolled, setIsScrolled] = useState(false);

    useEffect(() => {
        const updateActiveSection = () => {

            setIsScrolled(window.scrollY > 10);
            // Define the point on the screen where a section becomes "active" (35% from the top)
            const activationLine = window.scrollY + window.innerHeight * 0.35;
            // Detect if the user has hit the absolute bottom of the page
            const nearBottom = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 24;

            let nextActive = NAV_LINKS[0].href;

            for (const link of NAV_LINKS) {
                // Strip the '#' to get the actual DOM id (e.g., "#about" -> "about")
                const id = link.href.substring(1);
                const el = document.getElementById(id);

                if (!el) continue;

                // If the top of the element has crossed the activation line, it becomes active
                if (el.offsetTop <= activationLine) {
                    nextActive = link.href;
                }
            }

            // Force the last item to be active if scrolled to the absolute bottom
            if (nearBottom) {
                nextActive = NAV_LINKS[NAV_LINKS.length - 1].href;
            }

            console.log(nextActive)

            setActiveSection(nextActive);
        };

        // Run once on mount, then attach to scroll/resize
        updateActiveSection();
        window.addEventListener('scroll', updateActiveSection, { passive: true });
        window.addEventListener('resize', updateActiveSection);

        return () => {
            window.removeEventListener('scroll', updateActiveSection);
            window.removeEventListener('resize', updateActiveSection);
        };
    }, []); // Empty dependency array ensures this only binds once

    useEffect(() => {
        if (showMenus) {
            // Lock scrolling
            document.body.style.overflow = 'hidden';
        } else {
            // Restore scrolling
            document.body.style.overflow = '';
        }

        // Cleanup function ensures scrolling is restored if the component unmounts
        return () => {
            document.body.style.overflow = '';
        };
    }, [showMenus]);

    const handleSmoothScroll = (e: React.MouseEvent<HTMLAnchorElement, MouseEvent>, href: string) => {
        e.preventDefault();

        const id = href.substring(1);
        const element = document.getElementById(id);

        if (element) {
            // Header is roughly 80px tall. We subtract this so the header doesn't overlap the section title.
            const headerOffset = 100;
            const elementPosition = element.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.scrollY - headerOffset;

            window.scrollTo({
                top: offsetPosition,
                behavior: "smooth"
            });

            // Update URL hash without causing a jump
            window.history.pushState(null, "", href);
        }

        // Close mobile menu if it's open
        setShowMenus(false);
    };

    return (
        <div className={`w-full max-w-screen fixed flex items-center justify-center py-5 px-5 z-10 top-0`}>
            <div className={`w-screen h-22 fixed top-0 ${isScrolled ? "bg-background/90 backdrop-blur-md shadow-md border-b border-white/10" : "bg-transparent border-white/0 border-0 hidden"}`}>
                <br ></br>
                <br ></br>
                <br ></br>
                <br ></br>
            </div>
            <div className="w-280 max-w-full flex items-center justify-between relative">
                <Link href="/">
                    <Logo width={50} height={50} />
                </Link>

                <div className="hidden items-center justify-between gap-13 relative md:flex">
                    {NAV_LINKS.map((link) => {
                        // Check against our scroll state instead of the pathname
                        const isActive = activeSection === link.href;

                        return (
                            <Link
                                key={link.href}
                                href={link.href}
                                onClick={(e) => handleSmoothScroll(e, link.href)}
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
                <div className={`${showMenus ? "opacity-50" : "opacity-0 scale-[1.5] pointer-events-none z-1 "} duration-300 left-0 transition-all top-0 z-0 fixed w-screen h-screen bg-background blur-3xl`}>
                </div>
                <div className={`${showMenus ? "opacity-100" : "opacity-0 scale-[1.5] pointer-events-none z-2"} duration-300 left-0 flex transition-all top-0 z-1 fixed w-screen h-screen items-center justify-center flex-col gap-3 backdrop-blur-md`}>
                    <Logo width={45} height={45} className="mb-4" />

                    {NAV_LINKS.map((link) => {
                        const isActive = activeSection === link.href;

                        return (
                            <Link
                                key={link.href}
                                href={link.href}
                                className={` text-2xl relative pb-1 ${isActive ? "text-primary" : ""}`}
                                onClick={(e) => { setShowMenus(false); handleSmoothScroll(e, link.href); }}
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