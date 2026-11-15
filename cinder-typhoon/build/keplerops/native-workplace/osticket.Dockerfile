FROM alpine:3.19@sha256:6baf43584bcb78f2e5847d1de515f23499913ac9f12bdf834811a3145eb11ca1 AS source
RUN apk add --no-cache ca-certificates curl unzip \
    && curl -fsSL https://github.com/osTicket/osTicket/releases/download/v1.18.4/osTicket-v1.18.4.zip -o /tmp/osticket.zip \
    && echo 'a4187df5f52dd41625e6b61b322245853542e12b5969a45f0a6d81f7ab8151a7  /tmp/osticket.zip' | sha256sum -c - \
    && unzip -q /tmp/osticket.zip -d /opt/osticket

FROM php:8.4-apache-bookworm@sha256:5d55c49594dd833e2e4ff677b65f7d8ff48817f443a60691d9b2b382413bba42
RUN apt-get update \
    && apt-get install --no-install-recommends -y libfreetype6-dev libicu-dev libjpeg62-turbo-dev libonig-dev libpng-dev libzip-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j2 gd intl mbstring mysqli opcache zip \
    && apt-get clean \
    && a2enmod rewrite
COPY --from=source /opt/osticket/upload/ /var/www/html/
COPY build/keplerops/native-workplace/osticket-apache.conf /etc/apache2/conf-enabled/fieldlink-support.conf
COPY build/keplerops/native-workplace/install-support.php /opt/fieldlink/install-support.php
EXPOSE 80
