import { FieldType } from "@/_lib/types/EmbedLang";

export default function Field({ name, value, inline }: FieldType) {
    return (
        <span className={`${inline ? "col-span-1" : "col-span-3"} grid-cols-subgrid flex flex-col w-fit`}>
            <span className="font-bold!">{name}</span>
            <span>{value}</span>
        </span>
    )
}