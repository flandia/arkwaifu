FROM oven/bun:1.3.14 AS build

WORKDIR /app

COPY package.json bun.lock ./
RUN bun ci

COPY index.html vite.config.ts tsconfig*.json ./
COPY public ./public
COPY src ./src

RUN bun run build

FROM scratch AS artifact

COPY --from=build /app/dist /dist
