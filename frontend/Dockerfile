FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 4200

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "4200"]
