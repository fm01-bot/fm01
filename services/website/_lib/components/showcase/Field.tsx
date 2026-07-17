import { FieldType } from "@/_lib/Types";

export default function Field({ name, value, inline }: FieldType) {
    return (
        <span className={`${inline ? "col-span-1" : "col-span-3"} grid-cols-subgrid flex flex-col`}>
            <span className="font-bold!">{name}</span>
            <span>{value}</span>
        </span>
    )
}