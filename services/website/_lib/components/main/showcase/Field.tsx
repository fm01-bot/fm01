import { FieldType } from "@/_lib/types/EmbedLang";
import StringParser from "./StringParser";

export default function Field({ name, value, inline }: FieldType) {
    return (
        <span className={`embed-field ${inline ? "is-inline" : ""}`}>
            <span>{name}</span>
            <span><StringParser message={value} /></span>
        </span>
    )
}