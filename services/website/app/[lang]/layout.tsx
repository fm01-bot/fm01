import { ThemeProvider } from 'next-themes';
import '@lib/css/globals.css';
import Header from '@/_lib/tsx/Header';
import Footer from '@/_lib/tsx/Footer';
import { notFound } from 'next/navigation'
import { getDictionary, hasLocale } from './dictionaries'

export default async function Layout({
    children,
    params
}: LayoutProps<'/[lang]'>) {
    const { lang } = await params

    if (!hasLocale(lang)) notFound()

    const dict = await getDictionary(lang)

    return (

        <html lang={lang}>
            <body>
                <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
                    <Header lang={dict.header} />
                    <main>{children}</main>
                    <Footer lang={dict.footer} />
                </ThemeProvider>
            </body>
        </html>
    )
}