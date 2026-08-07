FROM php:8.2-apache
RUN docker-php-ext-install sockets
COPY . /var/www/html/
EXPOSE 80
