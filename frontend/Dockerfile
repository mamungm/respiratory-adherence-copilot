# Respiratory Adherence Copilot - frontend
# Multi-stage: build the Vite app, then serve the static output with nginx,
# which also reverse-proxies /api to the backend container (mirrors the
# vite dev server proxy in vite.config.js, which only applies to `npm run dev`).

FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
