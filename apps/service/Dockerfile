FROM ocaml/opam:alpine-3.23-ocaml-5.5 AS build

USER root
RUN apk add --no-cache libev-dev gmp-dev sqlite-dev openssl-dev pkgconf
USER opam

WORKDIR /home/opam/service

COPY --chown=opam:opam arkwaifu_service.opam dune-project ./
RUN opam install . --deps-only --with-test -y

COPY --chown=opam:opam lib ./lib
COPY --chown=opam:opam bin ./bin
COPY --chown=opam:opam test ./test
RUN opam exec -- dune runtest && opam exec -- dune build bin/main.exe

FROM build AS contract-test

COPY --from=database-schema --chown=opam:opam arkwaifu.sql /tmp/arkwaifu.sql
ENV ARKWAIFU_SCHEMA_PATH=/tmp/arkwaifu.sql
RUN opam exec -- dune runtest --force

FROM alpine:3.23 AS runtime

RUN apk add --no-cache ca-certificates libev sqlite-libs libssl3

COPY --from=build /home/opam/service/_build/default/bin/main.exe /usr/local/bin/arkwaifu-service

RUN adduser --disabled-password --gecos "" --uid 10001 arkwaifu
RUN install -d -o arkwaifu -g arkwaifu /var/lib/arkwaifu/database
USER 10001

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/arkwaifu-service"]
