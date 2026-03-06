FROM php:8.3-cli-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        gosu \
        unzip \
        zip \
        libicu-dev \
        libonig-dev \
        libxml2-dev \
        libzip-dev \
        libsqlite3-dev \
        libcurl4-openssl-dev \
        libpq-dev \
        autoconf \
        g++ \
        make \
        pkg-config \
    && docker-php-ext-install \
        bcmath \
        intl \
        mbstring \
        pcntl \
        pdo_mysql \
        pdo_pgsql \
        pdo_sqlite \
        curl \
        zip \
    && pecl install redis \
    && docker-php-ext-enable redis \
    && apt-get purge -y --auto-remove \
        autoconf \
        g++ \
        make \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g npm \
    && rm -rf /var/lib/apt/lists/*

COPY uploads.ini /usr/local/etc/php/conf.d/uploads.ini

WORKDIR /var/www/backend
