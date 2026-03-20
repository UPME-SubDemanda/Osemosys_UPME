### Stage 1: Build (Vite)
FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_APP_ENV=production
ARG VITE_SIMULATION_MODE=api

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_APP_ENV=${VITE_APP_ENV} \
    VITE_SIMULATION_MODE=${VITE_SIMULATION_MODE}

# Solo copiamos lo necesario primero para aprovechar cache.
COPY package*.json ./

# Builds reproducibles cuando existe lockfile.
RUN if [ -f package-lock.json ]; then npm ci; else npm install --no-audit --no-fund; fi

COPY . .

RUN npm run build

### Stage 2: Nginx (SPA)
FROM nginx:alpine AS runtime

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
