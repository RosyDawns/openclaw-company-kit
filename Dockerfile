FROM python:3.12-slim

WORKDIR /app

COPY dashboard/rd-dashboard /app/dashboard/rd-dashboard
COPY docker/demo_data /app/docker/demo_data
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN chmod +x /app/docker/entrypoint.sh

ENV DASHBOARD_PORT=8788
EXPOSE 8788

CMD ["/app/docker/entrypoint.sh"]
