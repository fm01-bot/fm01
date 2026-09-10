import { MessageType, ButtonType } from '@/_lib/types/MessageLang';
import { EmbedType } from '@/_lib/types/EmbedLang';
import Button from './Button';
import Embed from './Embed';
import Image from 'next/image';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheck } from '@fortawesome/free-solid-svg-icons';

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

    return (
        <>
            <div className='flex flex-row gap-2.5 justify-start'>
                <Image src={avatar} alt={`Avatar for ${username}`} width={38} height={38} className='rounded-full bg-text/20 h-fit w-fit' />
                <div className='flex flex-col'>
                    <div className={`flex flex-row ${bot ? "" : "gap-1"}`}>
                        <span className='text-primary/70'>{username}</span>
                        {bot ? (<div className='bg-[#5865F2] px-1.5 rounded-sm text-sm leading-6 font-bold scale-70 mt-px'><FontAwesomeIcon icon={faCheck} />APP</div>) : (<></>)}
                        <span className='text-xs mt-1.5 text-text/50'>{new Date().toLocaleDateString("en", { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div>
                        <span className='pb-2'>{message}</span>
                        {embeds?.map((e: EmbedType, i: number) => {
                            return <Embed key={i} {...e} />
                        })}
                        {
                            buttons?.map((r: [ButtonType?, ButtonType?, ButtonType?], i: number) => (
                                <div key={`row-${i}`} className="flex gap-2">
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