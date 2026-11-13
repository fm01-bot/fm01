import { ImageResponse } from 'next/og';
import fs from 'fs/promises';
import path from 'path';

// 1200×630 social preview card used by every page's og:image / twitter:image.
// Usage: /api/og?title=Features&description=Short+summary

const WIDTH = 1200;
const HEIGHT = 630;

// Dark theme tokens from globals.css (previews are always rendered dark).
const BG = '#1b1c1d';
const TEXT = '#f8fafc';
const PRIMARY = '#6094eb';

// Static Inter weights: the renderer (satori) can't read the variable public/fonts/Inter.ttf,
// and a font parse error there crashes the server process instead of returning a 500.
const read = (file: string) => fs.readFile(path.join(process.cwd(), 'public', file));
const assets = Promise.all([
    read('fonts/og/Inter-Regular.woff'),
    read('fonts/og/Inter-ExtraBold.woff'),
    read('fonts/og/Inter-Black.woff'),
    read('images/logo.png'),
]);

function clamp(value: string | null, fallback: string, max: number) {
    const text = (value ?? '').trim() || fallback;
    return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const title = clamp(searchParams.get('title'), 'fm01bot', 70);
    const description = clamp(searchParams.get('description'), 'Your all-in-one Discord bot.', 160);

    // Highlight the last word of the title, like the page headers do.
    const words = title.split(' ');
    const last = words.pop();

    const [regular, extraBold, black, logo] = await assets;
    const logoSrc = `data:image/png;base64,${logo.toString('base64')}`;

    return new ImageResponse(
        (
            <div
                style={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    padding: '72px 80px',
                    background: BG,
                    backgroundImage:
                        'linear-gradient(to right, rgba(248,250,252,0.04) 3px, transparent 1px), linear-gradient(to bottom, rgba(248,250,252,0.04) 3px, transparent 1px)',
                    backgroundSize: '121px 121px',
                    color: TEXT,
                    fontFamily: 'Inter',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={logoSrc} width={64} height={64} style={{ borderRadius: 14 }} alt="" />
                    <span style={{ fontSize: 48, fontWeight: 900, color: PRIMARY }}>fm01</span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                    <div
                        style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            fontSize: title.length > 32 ? 72 : 92,
                            fontWeight: 800,
                            lineHeight: 1,
                            letterSpacing: '-0.03em',
                        }}
                    >
                        {/* One span per word so the title wraps word by word. */}
                        {words.map((word, i) => (
                            <span key={i} style={{ marginRight: '0.25em' }}>{word}</span>
                        ))}
                        <span style={{ color: PRIMARY }}>{last}</span>
                    </div>
                    <div style={{ display: 'flex', fontSize: 32, lineHeight: 1.4, color: 'rgba(248,250,252,0.62)', maxWidth: 960 }}>
                        {description}
                    </div>
                </div>

                <div style={{ display: 'flex', fontSize: 26, color: 'rgba(248,250,252,0.45)' }}>fm01.bot</div>
            </div>
        ),
        {
            width: WIDTH,
            height: HEIGHT,
            fonts: [
                { name: 'Inter', data: regular, weight: 400, style: 'normal' },
                { name: 'Inter', data: extraBold, weight: 800, style: 'normal' },
                { name: 'Inter', data: black, weight: 900, style: 'normal' },
            ],
            headers: { 'Cache-Control': 'public, max-age=86400, s-maxage=604800' },
        }
    );
}
