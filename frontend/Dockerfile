FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json* ./

# npm registry for the install step. Override on networks where
# registry.npmjs.org is blocked, e.g. NPM_REGISTRY=https://registry.npmmirror.com
# (replace-registry-host rewrites the lockfile's npmjs URLs to the mirror).
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN npm config set registry "$NPM_REGISTRY" \
    && npm config set replace-registry-host always \
    && (npm ci || npm install)
COPY . .

# Vite inlines these values into the bundle at build time, so they must be
# available as build args (environment variables at `docker compose up` time
# are too late). All of them are public values; never pass secrets here.
ARG VITE_API_BASE_URL=""
ARG VITE_APP_ENV=production
ARG VITE_NESHAN_MAP_KEY=""
ARG VITE_MAP_CENTER_LAT=30.638
ARG VITE_MAP_CENTER_LNG=50.838
ARG VITE_MAP_DEFAULT_ZOOM=13
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_APP_ENV=$VITE_APP_ENV \
    VITE_NESHAN_MAP_KEY=$VITE_NESHAN_MAP_KEY \
    VITE_MAP_CENTER_LAT=$VITE_MAP_CENTER_LAT \
    VITE_MAP_CENTER_LNG=$VITE_MAP_CENTER_LNG \
    VITE_MAP_DEFAULT_ZOOM=$VITE_MAP_DEFAULT_ZOOM

RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
