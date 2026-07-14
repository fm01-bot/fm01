import { ChannelType } from '@/_lib/Types';
import Message from './Message';

export default function Channel({
    title,
    description,
    messages
}: ChannelType) {
    return (
        <div>
            <span>
                <span>#</span>
                {title}
                <span>·</span>
                {description}
            </span>
            {
                messages?.map((m, i) => {
                    return <Message key={`m-${i}`} {...m} />
                })
            }
        </div>
    )
}