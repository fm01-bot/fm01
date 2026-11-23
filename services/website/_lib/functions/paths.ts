import path from "path";

/**
 * The repo's `shared/` folder, for runtime file reads (imports use the `@shared/*` alias).
 * The site always runs from `services/website` (locally and in Docker, which mirrors the
 * repo layout), so this resolves to `<repo>/shared` or `/app/shared`.
 */
export const SHARED_DIR = path.resolve(process.cwd(), "../../shared");

/** Website translations: `<lang>.json` and the legal docs in `doc/<lang>/`. */
export const WEBSITE_L10N_DIR = path.join(SHARED_DIR, "localization", "website");
