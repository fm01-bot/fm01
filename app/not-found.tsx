import Link from 'next/link'
import { headers } from 'next/headers'
import { getDictionary, hasLocale } from './[lang]/dictionaries'

export default async function NotFound() {
    const headersList = await headers();
    const lang = headersList.get('x-locale') || 'en';
    const dictionary = hasLocale(lang)
        ? await getDictionary(lang)
        : undefined;
    const translation = dictionary?.notFound ?? {
        title: 'Not Found',
        description: 'Could not find requested resource.',
        home: 'Return Home',
    }

    return (
        <div>
            <h2>{translation.title}</h2>
            <p>{translation.description}</p>
            <Link href="/">
                {translation.home}
            </Link>
        </div>
    )
}