import { ButtonColors, ButtonType } from "@/_lib/Types"

export default function Button({
    label,
    url,
    emoji,
    color,
    disabled
}: ButtonType) {
    if (url && color) {
        throw new Error("A button can't have a preset color AND url at the same time.")
    }

    if (url && emoji) {
        throw new Error("A button can't have an emoji AND url at the same time.")
    }

    if (url) {
        return (
            <>
                {label}
                {url}
                {disabled}
            </>
        )
    }

    if (color) {
        return (
            <>
                {label}
                {color}
                {emoji}
                {disabled}
            </>
        )
    }

    return (
        <>
            {label}
            {emoji}
            {disabled}
        </>
    )
}