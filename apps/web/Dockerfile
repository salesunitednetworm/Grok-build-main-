FROM node:22-bookworm-slim

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ENV API_INTERNAL_URL=http://api:8000
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
