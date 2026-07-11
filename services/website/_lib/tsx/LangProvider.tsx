'use client';

import { createContext, useContext, ReactNode } from 'react';

// 1. Create the context OUTSIDE of any components
const LangContext = createContext('en');

// 2. Create the Provider component
export function LangProvider({ lang, children }: { lang: string; children: ReactNode }) {
    return <LangContext.Provider value={lang}>{children}</LangContext.Provider>;
}

// 3. Export a custom hook so your children components can easily use it
export const useLang = () => useContext(LangContext);