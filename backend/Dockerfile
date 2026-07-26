# Respiratory Adherence Copilot - backend API
FROM node:20-alpine

WORKDIR /app

# Install deps first so this layer is cached unless package.json changes
COPY package*.json ./
RUN npm install --omit=dev

COPY src ./src

ENV NODE_ENV=production
EXPOSE 4000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost:4000/api/health || exit 1

USER node

CMD ["node", "src/server.js"]
