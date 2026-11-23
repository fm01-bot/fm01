#!/usr/bin/env node
/**
 * Checks the website's localization against the bot's responses.
 *
 *   node services/website/scripts/check-localization.mjs   (or `pnpm check:l10n` in services/website)
 *
 * Errors (exit 1):
 *   - a showcase `botResponse`, `botText` or `botList` key that doesn't exist in the bot's English
 *     responses (English is the fallback, so a key missing there renders nothing);
 *   - a `botList` target that isn't a list of texts, or a `botText` target that isn't a text;
 *   - a `botResponse` target that isn't a response payload (object or embed list);
 *   - a `values` entry of an unknown shape.
 * Warnings:
 *   - a referenced key missing only in Hungarian (the page falls back to English);
 *   - keys present in one website language file but not the other;
 *   - legal docs present in `doc/en/` but not `doc/hu/`, or the other way round.
 *
 * Inside GitHub Actions, findings are also printed as annotations on the website JSON files.
 */
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const WEBSITE = 'shared/localization/website'
const RESPONSES = 'shared/localization/responses'
const LANGS = ['en', 'hu']
const FALLBACK = 'en'

const readJson = (file) => JSON.parse(readFileSync(path.join(REPO, file), 'utf8'))
const website = Object.fromEntries(LANGS.map((l) => [l, readJson(`${WEBSITE}/${l}.json`)]))
const responses = Object.fromEntries(LANGS.map((l) => [l, readJson(`${RESPONSES}/${l}.l10n.json`)]))

const findings = { error: [], warning: [] }
const inCi = process.env.GITHUB_ACTIONS === 'true'
function report(level, file, message) {
    findings[level].push(`${file}: ${message}`)
    if (inCi) console.log(`::${level} file=${file}::${message.replaceAll('\n', '%0A')}`)
}

const isObject = (v) => typeof v === 'object' && v !== null && !Array.isArray(v)
const isTextList = (v) => Array.isArray(v) && v.length > 0 && v.every((x) => typeof x === 'string')
const isPayload = (v) => isObject(v) || (Array.isArray(v) && v.every(isObject))

/** Same lookup as `getPathValue` in `_lib/functions/botResponses.ts`. */
function lookup(root, key) {
    return key.split('.').reduce((current, part) => (isObject(current) ? current[part] : undefined), root)
}

/** `a.b[0].c` style path, shared by every message so findings are easy to search for. */
const join = (at, key) => (typeof key === 'number' ? `${at}[${key}]` : at ? `${at}.${key}` : key)

/** Every object in `value` that has a `botResponse`, with its JSON path. */
function* references(value, at = '') {
    if (Array.isArray(value)) {
        for (const [i, item] of value.entries()) yield* references(item, join(at, i))
    } else if (isObject(value)) {
        if ('botResponse' in value) yield { message: value, at }
        for (const [key, child] of Object.entries(value)) yield* references(child, join(at, key))
    }
}

/* ---------- showcase references ---------- */

const KINDS = {
    botResponse: { valid: isPayload, what: 'a bot response (object or embed list)' },
    botText: { valid: (v) => typeof v === 'string', what: 'a text' },
    botList: { valid: isTextList, what: 'a non-empty list of texts' },
}

let referenceCount = 0
const missingInHu = new Map()

/** Checks `key` in the page's own language and in the English fallback. */
function checkKey(pageLang, file, where, kind, key) {
    referenceCount++
    if (typeof key !== 'string' || !key) {
        report('error', file, `${where}: "${kind}" must be a non-empty string`)
        return
    }
    for (const lang of new Set([FALLBACK, pageLang])) {
        const found = lookup(responses[lang], key)
        if (found === undefined) {
            if (lang === FALLBACK) report('error', file, `${where}: ${kind} "${key}" doesn't exist in ${RESPONSES}/${lang}.l10n.json`)
            else missingInHu.set(key, [...(missingInHu.get(key) ?? []), `${file} ${where}`])
            continue
        }
        if (!KINDS[kind].valid(found)) {
            report('error', file, `${where}: ${kind} "${key}" in ${RESPONSES}/${lang}.l10n.json isn't ${KINDS[kind].what}`)
        }
    }
}

for (const lang of LANGS) {
    const file = `${WEBSITE}/${lang}.json`
    for (const { message, at } of references(website[lang])) {
        checkKey(lang, file, at, 'botResponse', message.botResponse)
        if (message.values === undefined) continue
        if (!isObject(message.values)) {
            report('error', file, `${at}.values must be an object`)
            continue
        }
        for (const [name, spec] of Object.entries(message.values)) {
            const where = `${at}.values["${name}"]`
            if (typeof spec === 'string') continue
            if (isObject(spec) && 'botText' in spec) checkKey(lang, file, where, 'botText', spec.botText)
            else if (isObject(spec) && 'botList' in spec) checkKey(lang, file, where, 'botList', spec.botList)
            else if (isObject(spec) && Array.isArray(spec.randomInt) && spec.randomInt.length === 2
                && spec.randomInt.every(Number.isInteger) && spec.randomInt[0] <= spec.randomInt[1]
                && (spec.prefix === undefined || typeof spec.prefix === 'string')) continue
            else report('error', file, `${where}: expected a string, {botText}, {botList} or {randomInt: [min, max], prefix?}`)
        }
    }
}

for (const [key, places] of missingInHu) {
    report('warning', `${RESPONSES}/hu.l10n.json`, `"${key}" is missing; the Hungarian page shows English (${places.join(', ')})`)
}

/* ---------- website key parity ---------- */

/** Path of every object key and array item. Arrays are compared per index, since en and hu mirror each other. */
function keyPaths(value, at = '', out = new Set()) {
    const entries = Array.isArray(value) ? [...value.entries()] : isObject(value) ? Object.entries(value) : []
    for (const [key, child] of entries) {
        const next = join(at, key)
        out.add(next)
        keyPaths(child, next, out)
    }
    return out
}

const paths = Object.fromEntries(LANGS.map((l) => [l, keyPaths(website[l])]))
for (const lang of LANGS) {
    for (const other of LANGS.filter((l) => l !== lang)) {
        // Report only the topmost missing path, not every key under it.
        const missing = [...paths[lang]].filter((p) => !paths[other].has(p))
            .filter((p, _, all) => !all.some((q) => q !== p && (p.startsWith(`${q}.`) || p.startsWith(`${q}[`))))
        if (missing.length) {
            report('warning', `${WEBSITE}/${other}.json`, `${missing.length} key(s) in ${lang}.json missing here:\n  ${missing.join('\n  ')}`)
        }
    }
}

/* ---------- legal docs ---------- */

const docs = Object.fromEntries(LANGS.map((l) => [l, new Set(readdirSync(path.join(REPO, WEBSITE, 'doc', l)))]))
for (const lang of LANGS) {
    for (const other of LANGS.filter((l) => l !== lang)) {
        const missing = [...docs[lang]].filter((f) => !docs[other].has(f))
        if (missing.length) report('warning', `${WEBSITE}/doc/${other}`, `missing ${missing.join(', ')} (present in doc/${lang})`)
    }
}

/* ---------- summary ---------- */

if (!inCi) {
    for (const message of findings.warning) console.warn(`warning  ${message}`)
    for (const message of findings.error) console.error(`error    ${message}`)
}
console.log(`Checked ${referenceCount} bot response reference(s): ${findings.error.length} error(s), ${findings.warning.length} warning(s).`)
process.exit(findings.error.length ? 1 : 0)
