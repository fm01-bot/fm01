
"use client"
import { useState, useRef, useEffect, SetStateAction, Dispatch } from "react";
import { useRouter } from "next/navigation";

// Define the shape of our language object
interface Language {
    code: string;
    flag: string;
    name: string;
}

// Define the component's expected props
interface LanguageSelectorProps {
    currentLangCode?: string;
    mobileMenu?: [boolean, Dispatch<SetStateAction<boolean>>]
}

const LANGUAGES: Language[] = [
    { code: "en", flag: "🇬🇧", name: "English" },
    /*     { code: "de", flag: "🇩🇪", name: "Deutsch" },
        { code: "fr", flag: "🇫🇷", name: "Français" },
        { code: "es", flag: "🇪🇸", name: "Español" },
        { code: "it", flag: "🇮🇹", name: "Italiano" }, */
    { code: "hu", flag: "🇭🇺", name: "Magyar" },
];

export default function LangSelector({ currentLangCode = "en", mobileMenu }: LanguageSelectorProps) {
    const [isOpen, setIsOpen] = useState<boolean>(false);
    // Strongly type the ref to an HTMLDivElement
    const dropdownRef = useRef<HTMLDivElement>(null);

    const router = useRouter();
    const [isSwitching, setIsSwitching] = useState<boolean>(false);
    const currentLang = LANGUAGES.find((l) => l.code === currentLangCode) || LANGUAGES[0];

    useEffect(() => {
        // Strongly type the native DOM MouseEvent
        function handleClickOutside(event: MouseEvent) {
            // Cast event.target to Node so TypeScript knows it's valid for .contains()
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener("pointerdown", handleClickOutside);
        return () => document.removeEventListener("pointerdown", handleClickOutside);
    }, []);

    // The URL does not carry the locale, so switching means: persist the choice
    // in the cookie, then re-render the current route (proxy.tsx rewrites it to
    // the new locale). The refresh runs in a transition tagged "lang-switch",
    // which selects the circular reveal in app/layout.tsx.
    const handleLanguageSelect = (e: React.MouseEvent<HTMLButtonElement>, langCode: string) => {
        setIsOpen(false);
        if (langCode === currentLang.code || isSwitching) return;
        setIsSwitching(true);
        void (async () => {
            try {
                const response = await fetch("/api/locale", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ locale: langCode }),
                });
                if (!response.ok) throw new Error(`locale API ${response.status}`);
                router.refresh();
            } catch {
                setIsOpen(true);
            } finally {
                setIsSwitching(false);
            }
        })();
    };

    return (
        <div
            ref={dropdownRef}
            className="relative z-50 w-fit inline-flex items-center justify-between select-none transition-all duration-400 font-sans"
        >
            {/* Dropdown Trigger Button (Left side) */}
            <button
                type="button"
                aria-expanded={isOpen}
                aria-haspopup="listbox"
                className="flex items-center justify-center h-full rounded-l-[9px] transition-colors duration-200 cursor-pointer"
                onClick={() => setIsOpen((open) => !open)}
            >
                <span className="text-[20px] emoji">{currentLang.flag}</span>
                <svg
                    className={`w-2.5 h-2.5 text-text ml-2.5 transition-transform duration-200 ${isOpen ? "rotate-180 -translate-y-" : ""
                        }`}
                    fill="currentColor"
                    viewBox="0 0 700 700"
                >
                    <path d="m380.39 484.79 307.04-305.99c16.766-17.812 16.766-45.059 0-61.828-16.766-16.766-45.059-16.766-61.828 0l-275.6 275.6-275.6-275.6c-17.812-16.766-45.059-16.766-61.828 0-16.766 16.766-16.766 44.012 0 61.828l305.99 305.99c17.812 16.766 45.059 16.766 61.828 0z" />
                </svg>
            </button>

            {/* Dropdown Menu */}
            <div
                onPointerDown={(event) => event.stopPropagation()}
                className={`absolute -left-3.5 top-full transition-all duration-200 z-50 pointer-events-auto bg-text/10 rounded-lg backdrop-blur-sm border-background border ${isOpen
                    ? "top-[calc(100%+20px)] opacity-100 visible"
                    : "top-[calc(100%+30px)] opacity-0 invisible"
                    }`}
            >
                <ul className="flex flex-col w-full max-h-75 p-1.5 overflow-y-auto list-none whitespace-nowrap">
                    {LANGUAGES.map((lang) => (
                        <li key={lang.code}>
                            <button
                                type="button"
                                lang={lang.code}
                                aria-current={lang.code === currentLang.code ? "true" : undefined}
                                disabled={isSwitching}
                                onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
                                    e.stopPropagation();
                                    handleLanguageSelect(e, lang.code);
                                }}
                                className={`flex items-center w-full p-2 rounded-[5px] cursor-pointer transition-colors hover:bg-background/80 disabled:cursor-wait`}
                            >
                                <span className="inline-block mr-3.75 text-[18px] emoji">
                                    {lang.flag}
                                </span>
                                <span className="font-bold text-sm">
                                    {lang.code.toUpperCase()}
                                </span>
                            </button>
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}