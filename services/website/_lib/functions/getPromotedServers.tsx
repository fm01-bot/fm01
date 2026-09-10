'use server'

import { PromotedServersJson } from "@/_lib/types/MainPageLang"

export async function getPromotedServers() {

    const SERVERS: PromotedServersJson[] = [
        {
            count: 1000,
            invite: "https://fm01.bot",
            icon: "https://picsum.photos/1080/1080",
            name: "asd"
        },
        {
            count: 1000,
            invite: "https://fm01.bot",
            icon: "https://picsum.photos/1080/1080",
            name: "asd"
        },
        {
            count: 1000,
            invite: "https://fm01.bot",
            icon: "https://picsum.photos/1080/1080",
            name: "asd"
        },
        {
            count: 1000,
            invite: "https://fm01.bot",
            icon: "https://picsum.photos/1080/1080",
            name: "asd"
        },
        {
            count: 1000,
            invite: "https://fm01.bot",
            icon: "https://picsum.photos/1080/1080",
            name: "asd"
        },
        {
            count: 1000,
            invite: "https://fm01.bot",
            icon: "https://picsum.photos/1080/1080",
            name: "asd"
        },
        {
            count: 1000,
            invite: "https://fm01.bot",
            icon: "https://picsum.photos/1080/1080",
            name: "asd"
        }
    ]

    {/**
        TODO: Write DB function to get list of promoted servers
        
        JSON type:
        {
            count: number,
            name: string,
            invite: string,
            icon: string
        }
    */}

    return {
        SERVERS
    }
}