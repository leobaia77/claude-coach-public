# Claude-Coach dashboard — multi-user cloud image.
# Build context is the REPO ROOT (Railway: Dockerfile path dashboard/Dockerfile).
# templates/ is copied in because signup instantiates each new user's wiki from it.
FROM node:22-bookworm-slim

WORKDIR /app

# Install deps first for layer caching. better-sqlite3 ships prebuilt binaries
# for linux x64/arm64, so no build toolchain is needed.
COPY dashboard/package*.json ./dashboard/
RUN cd dashboard && npm ci

# App source + the wiki template new users are seeded from.
COPY dashboard/ ./dashboard/
COPY templates/ ./templates/

# Build the frontend (vite → dashboard/dist, served by Express).
RUN cd dashboard && npm run build

ENV NODE_ENV=production \
    DATA_DIR=/data \
    PORT=8787

EXPOSE 8787

WORKDIR /app/dashboard
CMD ["npx", "tsx", "server/index.ts"]
