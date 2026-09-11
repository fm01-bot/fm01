import { ChannelType } from '@/_lib/types/MainPageLang';
import Message from './Message';

export default function Channel({
    title,
    description,
    messages
}: ChannelType) {
    return (
        <div className='flex flex-col gap-3 w-full'>
            {
                messages?.map((m, i) => {
                    return <Message key={`m-${i}`} {...m} />
                })
            }
        </div>
    )
}