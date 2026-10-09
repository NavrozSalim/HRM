FROM node:20-alpine AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/40-hrm-config.sh /hrm-config.sh
COPY --from=build /app/dist /usr/share/nginx/html

RUN chmod 755 /hrm-config.sh

EXPOSE 80

CMD ["sh", "-c", "sh /hrm-config.sh && exec nginx -g 'daemon off;'"]
