ARG BASE_IMAGE=python@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
FROM ${BASE_IMAGE}
WORKDIR /app
COPY scripts/crux/feed.py scripts/crux/publisher.py ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
CMD ["python3","/app/publisher.py"]
