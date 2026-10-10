# Building from vanilla alpine base, as official Python
# alpine container is outdated and has 5 HIGH CVEs...
FROM alpine:latest

LABEL author="p1zzm1ssile"
LABEL org.opencontainers.image.source="https://github.com/p1zzm1ssile/Evictarr"
LABEL original_author="steveharsant (Purgarr)"
LABEL org.opencontainers.image.description='Evictarr: a maintained fork of Purgarr by Steve Harsant. Keeps your download client clean for Sonarr and Radarr.'

WORKDIR /app
COPY ./src .

RUN apk add python3 py3-pip
RUN pip install --no-cache-dir --break-system-packages -r /app/requirements.txt
HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
  CMD ["python", "healthcheck.py"]
CMD ["python", "main.py"]
