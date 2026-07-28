# Respiratory Adherence Copilot - backend API
#
# node:20-slim (Debian), not node:20-alpine: @xenova/transformers pulls in
# onnxruntime-node, whose prebuilt native binding targets glibc and can
# fail to load on musl-based Alpine. Slim avoids that at the cost of a
# somewhat larger image.
#
# @xenova/transformers also has a hard (not actually skippable, despite
# being listed as "optional") dependency on `sharp` for its image-utils
# module, which is imported eagerly even when you only use the text
# feature-extraction pipeline. `npm install` needs to be able to fetch
# sharp's prebuilt native binary during this build - fine on normal
# internet access, but worth knowing if this build ever fails inside a
# restrictive network/proxy.
FROM node:20-slim

WORKDIR /app

# Install deps first so this layer is cached unless package.json changes
COPY package*.json ./
RUN npm install --omit=dev

COPY src ./src
COPY scripts ./scripts

ENV NODE_ENV=production
EXPOSE 4000

# wget/curl aren't installed on node:20-slim by default - use Node itself
# instead of adding an apt-get layer just for the healthcheck.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:4000/api/health', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

USER node

CMD ["node", "src/server.js"]
