FROM node:22-alpine

WORKDIR /app

ENV HTTP_PROXY=http://http.docker.internal:3128
ENV HTTPS_PROXY=http://http.docker.internal:3128
ENV http_proxy=http://http.docker.internal:3128
ENV https_proxy=http://http.docker.internal:3128

COPY package.json ./

RUN npm install

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]