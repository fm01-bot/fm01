import { ThemeProvider } from 'next-themes';
import '@lib/css/globals.css';

export default function MainpageLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body>
                <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
                    <main>{children}</main>
                </ThemeProvider>
            </body>
        </html>
    )
}