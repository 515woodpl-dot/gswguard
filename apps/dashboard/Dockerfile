FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json ./
COPY apps/dashboard/package.json apps/dashboard/package-lock.json ./apps/dashboard/
COPY packages ./packages
COPY apps/dashboard ./apps/dashboard
RUN npm ci --prefix apps/dashboard
RUN npm --prefix apps/dashboard run build

FROM node:22-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production PORT=3000
COPY --from=build --chown=node:node /app/apps/dashboard/.next/standalone ./
COPY --from=build --chown=node:node /app/apps/dashboard/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
