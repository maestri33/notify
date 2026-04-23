FROM node:20-alpine

WORKDIR /app

# ffmpeg useful for baileys media normalization (not strictly required)
RUN apk add --no-cache ffmpeg git python3 make g++

COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

COPY index.js ./

RUN mkdir -p /data/auth

ENV PORT=3000 AUTH_DIR=/data/auth
EXPOSE 3000

CMD ["node", "index.js"]
