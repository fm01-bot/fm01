import { getPromotedServers } from "@/_lib/functions/getPromotedServers";
import { getStatsCount } from "@/_lib/functions/getStatsCount";
import Members from "@/_lib/svg/Members";
import { PromotedServersJson } from "@/_lib/types/MainPageLang";
import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import Image from "next/image";
import Link from "next/link";

export default async function PromotedServers({ lang }: { lang: MainPageLangJson["servers"] }) {

    const { SERVERS } = await getPromotedServers();

    const { COUNTS } = await getStatsCount();

    const ROWS = getRows();

    function getRows(): PromotedServersJson[][] {
        if (!SERVERS) return [];
        const rows: PromotedServersJson[][] = [[]];
        let row: number = 0;

        SERVERS.map((a: PromotedServersJson, i: number) => {
            if (i / 5 == Math.floor(i / 5)) {
                row++;
                rows.push([]);
            }
            console.log(row)
            rows[row].push(a)
        })

        console.log(rows);

        return rows;
    }

    return (
        <div id="features" className="h-fit">
            <p className="title">
                {lang.title}
            </p>
            <span className="trust-subtext">
                <span>
                    {`${lang.subtext[0]} `}
                </span>
                <span>
                    {`${COUNTS[0]}+`}
                </span>
                <span>
                    {` ${lang.subtext[1]} `}
                </span>
                <span>
                    {`${COUNTS[1]}+`}
                </span>
                <span>
                    {` ${lang.subtext[2]}`}
                </span>
            </span>
            <div className="flex flex-row flex-wrap gap-2 w-full max-w-full justify-center promoted-servers">
                {
                    ROWS.map((row: PromotedServersJson[], i: number) => {
                        return (
                            <div key={i} className="promoted-servers-row">
                                {
                                    row.map((s: PromotedServersJson, j: number) => {
                                        return (
                                            <Link href={s.invite} key={j} className="flex flex-row h-fit w-full p-4 pr-8 gap-2.5 bg-contrast rounded-2xl">
                                                <Image src={s.icon} alt={s.name} width={60} height={60} className="rounded-lg" />
                                                <div className="flex flex-col">
                                                    <span className="text-2xl font-semibold">{s.name}</span>
                                                    <span className="flex flex-row items-center gap-1">
                                                        <Members width={20} height={15} className="opacity-10 mt-1" />
                                                        <span className=" leading-[normal]! text-xl! font-light! opacity-50">{new Intl.NumberFormat().format(s.count)} {lang.memberstext}</span>
                                                    </span>
                                                </div>
                                            </Link>
                                        )
                                    })
                                }
                            </div>
                        )
                    })
                }
            </div>
        </div>
    );
}