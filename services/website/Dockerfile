# Build from the repo root so the image can see shared/:
#   docker build -f services/website/Dockerfile --target prod -t fm01-prod .
# The image mirrors the repo layout (/app/services/website + /app/shared), so the
# @shared/* alias and ../../shared runtime reads resolve the same way as locally.
FROM node:26-alpine3.23 AS base

WORKDIR /app/services/website

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

RUN npm install -g pnpm

FROM base AS deps

COPY services/website/package.json services/website/pnpm-lock.yaml services/website/pnpm-workspace.yaml ./

RUN pnpm install --frozen-lockfile

FROM base AS source

COPY --from=deps /app/services/website/node_modules ./node_modules
COPY shared/localization /app/shared/localization
COPY services/website ./

FROM source AS dev

ENV CI=true
ENV NODE_ENV=development

EXPOSE 3007

CMD ["pnpm", "run", "dev"]

FROM source AS build

ENV CI=true

RUN pnpm run build

FROM build AS prod

ENV NODE_ENV=production

EXPOSE 3007

CMD ["pnpm", "run", "start"]
