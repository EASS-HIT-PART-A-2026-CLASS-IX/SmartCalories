FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE=http://localhost:9000
ARG VITE_FB_API_KEY=
ARG VITE_FB_AUTH_DOMAIN=
ARG VITE_FB_PROJECT_ID=
ARG VITE_FB_APP_ID=
ENV VITE_API_BASE=$VITE_API_BASE \
    VITE_FB_API_KEY=$VITE_FB_API_KEY \
    VITE_FB_AUTH_DOMAIN=$VITE_FB_AUTH_DOMAIN \
    VITE_FB_PROJECT_ID=$VITE_FB_PROJECT_ID \
    VITE_FB_APP_ID=$VITE_FB_APP_ID
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
