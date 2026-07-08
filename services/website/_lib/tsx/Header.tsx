"use client"
import Image from "next/image";
import logo from "@public/logo.png"
import Link from "next/link";
import { usePathname } from 'next/navigation'
import { motion } from 'framer-motion';

const NAV_LINKS = [
    { href: "/", label: "Home" },
    { href: "/about", label: "About" },
    { href: "/features", label: "Features" },
    { href: "/status", label: "Status" },
    { href: "/pricing", label: "Pricing" },
];

export default function Header() {
    const page = usePathname();

    return (
        <div className="w-full flex items-center justify-center py-2">
            <div className="w-275 flex items-center justify-between relative">
                <Link href="/">
                    <Image src={logo} width={45} height={45} alt="fm01bot logoja" />
                </Link>

                <div className="flex items-center justify-between gap-13 relative">
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

                <Link href="https://fm01.bot" className="bg-primary px-4 py-1 rounded-md text-white">
                    Dashboard
                </Link>
            </div>
        </div>
    )
}