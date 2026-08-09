FROM node:22-alpine

WORKDIR /app

# Copy only package files first for layer caching
COPY package.json package-lock.json ./

# Install deps (omit @portalsdk/* if unavailable — optional local packages)
RUN npm install --legacy-peer-deps 2>/dev/null; npm install

COPY . .

EXPOSE 3000

CMD ["npx", "next", "dev", "-H", "0.0.0.0", "-p", "3000"]
