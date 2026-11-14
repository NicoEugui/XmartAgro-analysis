FROM python:3.12-slim AS build
WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=build /install /usr/local
RUN useradd --system --uid 10001 worker
USER worker
ENTRYPOINT ["xmart-analysis-worker"]
CMD ["--loop"]
