# Frontend container (Step 16) — static configuration, NOT runtime-verified
# in this environment (Docker unavailable). Build args carry no secrets; the
# API base URL defaults to same-origin behind the bundled nginx proxy.
FROM node:24-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
# Minimal same-origin proxy: /api → backend service (no secrets in config).
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
