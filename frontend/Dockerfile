FROM nginx:1.27-alpine

# Remove config padrão do nginx
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/app.conf

# Copia os arquivos estáticos do frontend
COPY . /usr/share/nginx/html

EXPOSE 80
