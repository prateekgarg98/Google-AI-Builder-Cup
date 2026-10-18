# ---------- Build stage ----------
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests
COPY package*.json ./
RUN npm ci

# Copy source code and build React frontend
COPY . .
RUN npm run build


# ---------- Production stage ----------
FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=8080

# Install only production dependencies (Express)
COPY package*.json ./
RUN npm ci --omit=dev

# Copy built React UI from builder stage
COPY --from=builder /app/dist ./dist

# Copy Express backend server
COPY server.js ./

EXPOSE 8080

CMD ["node", "server.js"]