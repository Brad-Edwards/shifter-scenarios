FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS content-builder
RUN pip install --no-cache-dir PyYAML reportlab
WORKDIR /build
COPY build/A0-boreas-website/build_pdfs.py .
COPY contract_source.py .
# The canonical placement contract supplies the annual-report flag.
COPY flags/placement.yaml .
RUN python build_pdfs.py /build/out

FROM nginx:alpine@sha256:4a73073bd557c65b759505da037898b61f1be6cbcc3c2c3aeac22d2a470c1752
COPY build/A0-boreas-website/site/ /usr/share/nginx/html/
COPY --from=content-builder /build/out/internal/ /usr/share/nginx/html/internal/
COPY build/a0/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
