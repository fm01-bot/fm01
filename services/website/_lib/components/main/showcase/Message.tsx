import { MessageType, ButtonType } from '@/_lib/types/MessageLang';
import { EmbedType } from '@/_lib/types/EmbedLang';
import Button from './Button';
import Embed from './Embed';
import Image from 'next/image';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheck } from '@fortawesome/free-solid-svg-icons';
import StringParser from './StringParser';
import '@lib/css/main/showcase.css';

export default function Message({
    message,
    embeds,
    buttons,
    username,
    avatar,
    bot
}: MessageType) {
    if (embeds && buttons) {
        throw new Error("You can't have buttons AND embeds at the same time! Use buttons within the embeds!")
    }

    const today = new Date();

    return (
        <>
            <div className='message'>
                <Image src={avatar} alt={`Avatar for ${username}`} width={38} height={38} className='message-avatar w-[38px]! h-[38px]!' />
                <div className='message-body'>
                    <div className={`message-header ${bot ? "is-bot" : ""}`}>
                        <span className='message-username'>{username}</span>
                        {bot ? (
                            <div className='app-badge'>
                                <FontAwesomeIcon icon={faCheck} />
                                <span>APP</span>
                            </div>) : (<></>)}
                        <span className='message-time'>{today.toLocaleDateString("en", { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div>
                        <div className='message-text'>
                            <StringParser message={message} />
                        </div>
                        {embeds?.map((e, i) => {
                            if (typeof e === "string") return
                            return <Embed key={i} {...e} />
                        })}
                        {
                            buttons?.map((r: [ButtonType?, ButtonType?, ButtonType?], i: number) => (
                                <div key={`row-${i}`} className="button-row">
                                    {r.map((b: ButtonType | undefined, j: number) => {
                                        if (!b) return null;
                                        return <Button key={`btn-${i}-${j}`} {...b} />
                                    })}
                                </div>
                            ))
                        }
                    </div>
                </div>
            </div>
        </>
    )
}