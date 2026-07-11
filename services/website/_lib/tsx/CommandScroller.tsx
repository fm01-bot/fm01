const commandsData = [
    { name: "ban", params: "[user] <indok>", description: "Véglegesen kitilt egy felhasználót a szerverről." },
    { name: "kick", params: "[user] <indok>", description: "Kirúg egy felhasználót a szerverről, aki később visszatérhet." },
    { name: "mute", params: "[user] [idő] <indok>", description: "Megakadályozza, hogy egy felhasználó üzeneteket küldjön vagy beszéljen." },
    { name: "warn", params: "[user] <indok>", description: "Hivatalos figyelmeztetést ad egy szabálysértő felhasználónak." },
    { name: "purge", params: "[szám]", description: "Töröl egy megadott számú legutóbbi üzenetet a csatornából." },
    { name: "userinfo", params: "<user>", description: "Részletes információkat jelenít meg egy specifikus felhasználóról." },
    { name: "play", params: "[index]", description: "Elindítja a megadott zenét a csatlakozott hangcsatornában." },
    { name: "ticket", params: "", description: "Létrehoz egy privát támogatói csatornát a szerver moderátoraival." }
];
const prefix = "/";

export default function CommandScroller() {
    return (
        <div className="relative w-full max-w-110 mx-auto flex justify-start">

            <div
                className="w-108 z-10 h-122 relative overflow-hidden"
                style={{
                    WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 15%, black 85%, transparent)',
                    maskImage: 'linear-gradient(to bottom, transparent, black 15%, black 85%, transparent)'
                }}
            >

                { }
                <div className="flex flex-col gap-4 py-4 animate-[scroll-vertical_25s_linear_infinite] hover:[animation-play-state:paused]">

                    { }
                    {[...commandsData, ...commandsData].map((cmd, index) => (
                        <div
                            key={index}
                            className="group bg-background border border-text/40 rounded-xl p-5 flex flex-col gap-2 transition-all duration-200 shadow-md text-left hover:bg-text/3 hover:border-primary"
                        >
                            <div className="text-secondary font-extrabold! text-[2rem] flex flex-row gap-1 items-center">
                                {prefix}{cmd.name} <p className="opacity-0 group-hover:opacity-100 text-sm font-light">{cmd.params}</p>
                            </div>
                            <div className="secondary-text text-base! text-[0.95rem] leading-relaxed group-hover:text-text!">
                                {cmd.description}
                            </div>
                        </div>
                    ))}

                </div>
            </div>

            { }
            <style>{`
                @keyframes scroll-vertical {
                    0% { transform: translateY(0); }
                    100% { transform: translateY(-50%); }
                }
            `}</style>
        </div>
    );
}