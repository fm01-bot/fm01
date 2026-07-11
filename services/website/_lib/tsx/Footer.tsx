import logo from "@public/logo.png"
import Image from "next/image";
import Link from "next/link";

export default function Footer() {
    const currentYear = new Date().getFullYear();
    return (
        <div className="w-full flex items-center justify-center pb-5 px-5 flex-col py-10 md:pt-20 bg-text/7 md:[clip-path:polygon(0_0,100%_20%,100%_100%,0_100%)] [clip-path:polygon(0_0,100%_10%,100%_100%,0_100%)] pt-15">
            <div className="w-full max-w-275 flex items-center justify-around relative flex-wrap gap-10">
                <div>
                    <Image src={logo} width={75} height={75} alt="fm01bot logoja" />
                </div>
                <div>
                    <h1 className="pb-2">Kapcsolat</h1>
                    <p>Erdei Olivér Márton E.V.</p>
                    <p>Budapest, Perényi Zsigmond u. 25, 1047</p>
                    <Link href={`mailto:support@fm01.bot`} className="link">support@fm01.bot</Link>
                    <br />
                    <Link className="link" href={`https://dc.fm01.bot/`}>Discord Csatlakozás</Link>
                </div>

                <div>
                    <h1 className="pb-2">Dokumentumok</h1>
                    <p>Általános Szerződési Feltételek</p>
                    <p>Adatvédelmi Tájékoztató</p>
                    <p>Sütikezelési Tájékoztató</p>
                    <Link href={`https://github.com/fm01-bot`}>Github</Link>
                </div>
            </div>
            <div className="w-full max-w-275 flex items-center justify-around text-sm pt-5 flex-wrap gap-5">
                <div>
                    © {currentYear} fm01bot. Minden jog fenntartva.
                </div>
                <div>
                    Design by <Link className="link" href={`https://adam.ysit.ee/`}>Ace</Link>
                </div>
                <div>
                    Üzemeltető <Link className="link" href={`https://playclan.org`}>Erdei Olivér Márton E.V.</Link>
                </div>
            </div>
        </div>
    )
}