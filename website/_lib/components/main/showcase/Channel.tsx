import { ChannelType } from '@/_lib/types/MainPageLang';
import Message from './Message';
import '@lib/css/main/showcase.css';

export default function Channel({
    title,
    description,
    messages
}: ChannelType) {
    return (
        <div className='message-container'>
            {
                messages?.map((m, i) => {
                    return <Message key={`m-${i}`} {...m} />
                })
            }
        </div>
    )
}