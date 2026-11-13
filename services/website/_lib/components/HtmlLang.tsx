'use client'

import { useLayoutEffect } from 'react';

/** Keeps <html lang> in sync with the [lang] segment on client-side navigations
 *  (the attribute is rendered by app/layout.tsx, which does not re-render then). */
export default function HtmlLang({ lang }: { lang: string }) {
    useLayoutEffect(() => {
        document.documentElement.lang = lang;
    }, [lang]);
    return null;
}
