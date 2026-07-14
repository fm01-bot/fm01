import { ContainerType } from "@/_lib/Types";
import Channel from "./Channel";

export default function Container({ lang }: { lang?: ContainerType }) {
    return (
        <>
            {
                lang?.channels?.map((c, i) => {
                    return <Channel key={`c-${i}`} {...c} />
                })
            }
        </>
    )
}