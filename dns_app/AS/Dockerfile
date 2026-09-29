# Author: Ziyi Liu (zl6722)
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY common.py server.py ./
RUN mkdir /data && chown -R 10001:10001 /app /data
USER 10001:10001
ENV PORT=53533
ENV DB_PATH=/data/records.sqlite3
EXPOSE 53533/udp
CMD ["python", "server.py"]
