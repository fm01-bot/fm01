import '@lib/css/globals.css';
import Header from '@/_lib/components/Header';
import Footer from '@/_lib/components/Footer';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from './dictionaries';
import { ThemeProvider } from '@teispace/next-themes';
import { getTheme } from '@teispace/next-themes/server';
import type { Metadata } from 'next';

type LayoutProps = {
    children: React.ReactNode;
    params: Promise<{ lang: string }>;
};

export const metadata: Metadata = {
    title: 'fm01bot',
    description: 'fm01bot, utility for your server.',
    icons: {
        icon: [
            { url: '/favicons/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
            { url: '/favicons/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
        ],
        apple: [
            { url: '/favicons/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
        ],
    },
    manifest: '/favicons/site.webmanifest',
};

export default async function Layout({
    children,
    params
}: LayoutProps) {
    const { lang } = await params;

    if (!hasLocale(lang)) notFound();

    const dict = await getDictionary(lang);

    const initialTheme = await getTheme();

    return (
        < html lang={lang} suppressHydrationWarning >
            <body>
                <ThemeProvider
                    attribute="class"
                    defaultTheme="system"
                    enableSystem={true}
                    initialTheme={initialTheme ?? undefined}
                >
                    <Header lang={dict.header} code={lang} />
                    <main>{children}</main>
                    <Footer lang={dict.footer} />
                </ThemeProvider>
            </body>
        </html>
    );
}