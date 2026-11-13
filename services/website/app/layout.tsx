import '@lib/css/globals.css';
import { headers } from 'next/headers';
import { ThemeProvider } from '@teispace/next-themes';
import { getTheme } from '@teispace/next-themes/server';
import { ViewTransition } from 'react';

/**
 * Root layout: owns <html>/<body>, the theme provider and the page transition
 * boundary. It deliberately sits above the [lang] segment so that switching
 * language only swaps the content inside the boundary. If <html> lived in the
 * [lang] layout, React would remount it on every language switch and wipe the
 * attributes it did not render (theme class, inline styles, ...).
 *
 * The locale for <html lang> comes from the x-locale header set in proxy.tsx;
 * <HtmlLang> in the [lang] layout keeps it in sync on client-side navigations.
 */
export default async function RootLayout({ children }: { children: React.ReactNode }) {
    const lang = (await headers()).get('x-locale') ?? 'en';
    const initialTheme = await getTheme();

    return (
        <html lang={lang} suppressHydrationWarning>
            <body>
                <ThemeProvider
                    attribute="class"
                    defaultTheme="system"
                    enableSystem={true}
                    initialTheme={initialTheme ?? undefined}
                    disableTransitionOnChange
                    transition={{ type: 'circular', duration: 500, easing: 'ease-in-out', origin: 'cursor' }}
                >
                    {/* One transition group for the whole page (see globals.css "Page
                        transitions"): ordinary navigations cross-fade ("vt-page"); a
                        navigation started with addTransitionType('lang-switch') gets the
                        circular reveal ("vt-reveal"). */}
                    <ViewTransition default={{ default: 'vt-page', 'lang-switch': 'vt-reveal' }}>
                        <div data-vt-root className="flex flex-col flex-1 min-h-screen">
                            {children}
                        </div>
                    </ViewTransition>
                </ThemeProvider>
            </body>
        </html>
    );
}
