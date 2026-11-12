FROM frangoteam/fuxa:1.3.5@sha256:931781ce0557304d5b3b51e3d2ddb180dd2252b5e4b9936be7fd935bf5c62a2a
WORKDIR /usr/src/app/FUXA/server/_pkg/runtime
COPY fuxa-plugin/package*.json ./
RUN npm ci --omit=dev --no-audit --no-fund
WORKDIR /usr/src/app/FUXA/server
