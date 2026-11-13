'use client'

import { useTheme } from '@teispace/next-themes';
import { useEffect, useState } from 'react'

export default function ThemeToggle() {
    const { setTheme } = useTheme()
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        requestAnimationFrame(() => {
            setMounted(true)
        })
    }, [])

    if (!mounted) {
        return <div className="h-10 w-32 opacity-0"></div>
    }

    return (
        <div className="flex gap-2 p-2">
            <button
                onClick={() => setTheme('light')}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors bg-primary text-white hover:opacity-90`}
            >
                Light
            </button>

            <button
                onClick={() => setTheme('dark')}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors bg-secondary text-white hover:opacity-90`}
            >
                Dark
            </button>

            <button
                onClick={() => setTheme('system')}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors border-2 border-accent text-accent hover:bg-accent hover:text-white`}
            >
                System
            </button>
        </div>
    )
}