FROM python:3.10-slim AS build

RUN pip3 install poetry
WORKDIR /src
ADD . /src
RUN poetry install
RUN poetry build -f wheel


FROM python:3.10-slim

WORKDIR /pkg
COPY --from=build /src/dist/prusa_exporter*.whl /pkg/
RUN pip3 install prusa_exporter*.whl
EXPOSE 9789
ENTRYPOINT ["python3", "-u", "-m", "prusa_exporter"]
