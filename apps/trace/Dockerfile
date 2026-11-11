FROM python:3.13-alpine
WORKDIR /app
COPY app.py index.html ./
ENV PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
EXPOSE 8094
CMD ["python", "-u", "app.py"]
