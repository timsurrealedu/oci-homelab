FROM python:3.13-alpine
RUN apk add --no-cache iputils mtr bind-tools
WORKDIR /app
COPY app.py index.html ./
ENV PYTHONDONTWRITEBYTECODE=1
EXPOSE 8090
# Root inside the container, but compose drops every capability except NET_RAW (ping, mtr).
CMD ["python", "-u", "app.py"]
