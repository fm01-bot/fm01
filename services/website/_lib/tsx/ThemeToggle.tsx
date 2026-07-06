'use client'

import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'

export default function ThemeToggle() {
    const { theme, setTheme } = useTheme()
    const [mounted, setMounted] = useState(false)

    // useEffect only runs on the client, so now we can safely show the UI
    useEffect(() => {
        requestAnimationFrame(() => {
            setMounted(true)
        })
    }, [])

    if (!mounted) {
        // Return a placeholder of the exact same size to prevent layout shift on load
        return <div className="h-10 w-32 opacity-0"></div>
    }

    return (
        <div className="flex gap-2 p-2 bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-300 dark:border-gray-700">
            <button
                onClick={() => setTheme('light')}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${theme === 'light' ? 'bg-white text-black shadow-sm' : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'
                    }`}
            >
                Light
            </button>

            <button
                onClick={() => setTheme('dark')}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${theme === 'dark' ? 'bg-gray-700 text-white shadow-sm' : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'
                    }`}
            >
                Dark
            </button>

            <button
                onClick={() => setTheme('system')}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${theme === 'system' ? 'bg-white dark:bg-gray-700 text-black dark:text-white shadow-sm' : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'
                    }`}
            >
                System
            </button>
        </div>
    )
}