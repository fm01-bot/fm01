import '@lib/css/globals.css';
import Header from '@/_lib/tsx/Header';
import Footer from '@/_lib/tsx/Footer';
import { use } from 'react';
import hu_lang from "@lib/translations/hu.json";
import en_lang from "@lib/translations/en.json";
import { LangProvider } from '@/_lib/tsx/LangProvider';
import { ThemeProvider } from '@/_lib/tsx/ThemeProvider';

export default function Layout({
    children,
    params
}: {
    children: React.ReactNode,
    params: Promise<{ lang: string }>
}) {
    const langs = ["en", "hu"]
    let { lang } = use(params);
    lang = lang.substring(0, 2);
    if (!langs.includes(lang)) {
        lang = "en";
    }

    const lang_json = lang === 'en' ? en_lang : hu_lang;

    return (
        <html lang={lang}>
            <body>
                <LangProvider lang={lang}>
                    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
                        <div className='flex flex-col min-h-screen m-auto px-8 md:px-96 no-scrollbar gap-48'>
                            <nav className='relative z-1'>
                                <Header lang={lang_json.header} />
                            </nav>
                            <main className='h-full flex'>
                                <div className='w-275'>
                                    {children}
                                </div>
                            </main>
                        </div>
                        <footer className='bottom-0 relative mt-auto z-0 '>
                            <Footer />
                        </footer>
                    </ThemeProvider>
                </LangProvider>
            </body>
        </html>
    );
}