import { ThemeProvider } from 'next-themes';
import '@lib/css/globals.css';
import Header from '@/_lib/tsx/Header';
import Footer from '@/_lib/tsx/Footer';

export default function Layout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body className='px-5'>
                <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
                    <Header />
                    <main>{children}</main>
                    <Footer />
                </ThemeProvider>
            </body>
        </html>
    )
}