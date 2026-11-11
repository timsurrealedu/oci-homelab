FROM python:3.13-alpine
WORKDIR /app
COPY app.py ./
ENV PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
CMD ["python", "-u", "app.py"]
