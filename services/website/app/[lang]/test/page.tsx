
"use client"
import { useState, useRef, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";

// Define the shape of our language object
interface Language {
    code: string;
    flag: string;
    name: string;
}

// Define the component's expected props
interface LanguageSelectorProps {
    currentLangCode?: string;
}

const LANGUAGES: Language[] = [
    { code: "en", flag: "🇬🇧", name: "English" },
    /*     { code: "de", flag: "🇩🇪", name: "Deutsch" },
        { code: "fr", flag: "🇫🇷", name: "Français" },
        { code: "es", flag: "🇪🇸", name: "Español" },
        { code: "it", flag: "🇮🇹", name: "Italiano" }, */
    { code: "hu", flag: "🇭🇺", name: "Magyar" },
];

export default function Page({ currentLangCode = "en" }: LanguageSelectorProps) {
    const [isOpen, setIsOpen] = useState<boolean>(false);
    // Strongly type the ref to an HTMLDivElement
    const dropdownRef = useRef<HTMLDivElement>(null);

    const router = useRouter();
    const pathname = usePathname();

    const page = pathname.substring(3);

    const currentLang = LANGUAGES.find((l) => l.code === currentLangCode) || LANGUAGES[0];

    useEffect(() => {
        // Strongly type the native DOM MouseEvent
        function handleClickOutside(event: MouseEvent) {
            // Cast event.target to Node so TypeScript knows it's valid for .contains()
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const handleLanguageSelect = (langCode: string) => {
        setIsOpen(false);
        router.replace(`/${langCode}${page}`);
    };

    return (
        <div
            ref={dropdownRef}
            className="relative w-fit inline-flex items-center justify-between select-none transition-all duration-400 font-sans cursor-pointer mt-30"
            onClick={() => setIsOpen(!isOpen)}
        >
            {/* Dropdown Trigger Button (Left side) */}
            <div className="flex items-center justify-center px-2.5 h-full rounded-l-[9px] transition-colors duration-200">
                <span className="text-[20px]">{currentLang.flag}</span>
                <svg
                    className={`w-2.5 h-2.5 text-text ml-2.5 transition-transform duration-200 ${isOpen ? "rotate-180 -translate-y-" : ""
                        }`}
                    fill="currentColor"
                    viewBox="0 0 700 700"
                >
                    <path d="m380.39 484.79 307.04-305.99c16.766-17.812 16.766-45.059 0-61.828-16.766-16.766-45.059-16.766-61.828 0l-275.6 275.6-275.6-275.6c-17.812-16.766-45.059-16.766-61.828 0-16.766 16.766-16.766 44.012 0 61.828l305.99 305.99c17.812 16.766 45.059 16.766 61.828 0z" />
                </svg>
            </div>

            {/* Dropdown Menu */}
            <div
                className={`absolute left-0 transition-all duration-200 z-10 bg-background/20 backdrop-blur-lg rounded-lg border-background border ${isOpen
                    ? "top-[calc(100%+5px)] opacity-100 visible"
                    : "top-[calc(100%+20px)] opacity-0 invisible"
                    }`}
            >
                <ul className="flex flex-col w-full max-h-75 p-1.5 overflow-y-auto list-none whitespace-nowrap">
                    {LANGUAGES.map((lang) => (
                        <li
                            key={lang.code}
                            onClick={(e: React.MouseEvent<HTMLLIElement>) => {
                                e.stopPropagation();
                                handleLanguageSelect(lang.code);
                            }}
                            className={`flex items-center p-2 rounded-[5px] cursor-pointer transition-colors hover:bg-background/80`}
                        >
                            <span className="inline-block mr-3.75 text-[18px]">
                                {lang.flag}
                            </span>
                            <span className="font-bold text-sm">
                                {lang.code.toUpperCase()}
                            </span>
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}