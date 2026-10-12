# Pin BASE_IMAGE by digest and CHROME_SHA256 after reviewing the build inputs.
ARG BASE_IMAGE=node@sha256:d8e448a56fc63242f70026718378bd4b00f8c82e78d20eefb199224a4d8e33d8
FROM ${BASE_IMAGE}
ARG CHROME_SHA256=a4edbe95e9b01db6c9b97d7a1323121eda18362b5620df06abac1b59bee80053
ARG CHROME_DEB_URL=https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_154.0.8037.97-1_amd64.deb
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl python3 xvfb xauth fonts-liberation \
 && test -n "$CHROME_SHA256" \
 && curl --fail --location "$CHROME_DEB_URL" --output /tmp/chrome.deb \
 && echo "$CHROME_SHA256  /tmp/chrome.deb" | sha256sum --check \
 && apt-get install -y --no-install-recommends /tmp/chrome.deb \
 && rm -rf /var/lib/apt/lists/* /tmp/chrome.deb
WORKDIR /app
COPY deploy/crux/package*.json ./
RUN npm ci --ignore-scripts --omit=dev && npm cache clean --force
COPY scripts/crux/collector.cjs scripts/crux/feed.py scripts/crux/worker.py scripts/crux/health.py ./
ENV TZ=America/Chicago PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
CMD ["python3","/app/worker.py"]
