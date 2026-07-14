import { MessageType } from '@/_lib/Types';
import Button from './Button';
import Embed from './Embed';

export default function Message({
    message,
    embeds,
    buttons,
    username,
    avatar
}: MessageType) {
    if (embeds && buttons) {
        throw new Error("You can't have buttons AND embeds at the same time! Use buttons within the embeds!")
    }

    return (
        <>
            {username}
            {avatar}
            {message}
            {embeds?.map((e, i) => {
                return <Embed key={i} {...e} />
            })}
            {
                buttons?.map((r, i) => (
                    <div key={`row-${i}`} className="flex gap-2">
                        {r.map((b, j) => {
                            if (!b) return null;
                            return <Button key={`btn-${i}-${j}`} {...b} />
                        })}
                    </div>
                ))
            }
        </>
    )
}