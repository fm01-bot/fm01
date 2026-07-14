import { FieldType } from "@/_lib/Types";

export default function Field({ name, value, inline }: FieldType) {
    return (
        <>
            {name}
            {value}
            {inline}
        </>
    )
}