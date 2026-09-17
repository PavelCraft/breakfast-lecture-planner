#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-markdown-integration}"
HEALTHCHECK_URL="${DEPLOY_HEALTHCHECK_URL:-https://malone.guru/}"
HEALTHCHECK_RESOLVE="${DEPLOY_HEALTHCHECK_RESOLVE:-malone.guru:443:127.0.0.1}"
BACKUP_DIR="${PROJECT_DIR}/backups"
DEPLOY_STATE="${PROJECT_DIR}/.deploy-state"
COMPOSE=(docker compose --project-directory "${PROJECT_DIR}")

cd "${PROJECT_DIR}"

if [[ ! -f .env ]]; then
    echo "Ошибка: ${PROJECT_DIR}/.env не найден." >&2
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Ошибка: на сервере есть незакоммиченные изменения." >&2
    echo "Разберите их перед деплоем, чтобы они не были потеряны." >&2
    git status --short >&2
    exit 1
fi

on_error() {
    exit_code=$?
    echo "Деплой завершился с ошибкой. Последние логи приложения:" >&2
    "${COMPOSE[@]}" logs --tail=100 breakfast_lecture_planner >&2 || true
    exit "${exit_code}"
}

trap on_error ERR

echo "Создание резервной копии PostgreSQL..."
mkdir -p "${BACKUP_DIR}"
previous_commit="$(git rev-parse HEAD)"
backup_file="${BACKUP_DIR}/database-$(date +%Y%m%d-%H%M%S).dump"
"${COMPOSE[@]}" exec -T postgres \
    sh -c 'pg_dump --format=custom -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    > "${backup_file}"
"${COMPOSE[@]}" exec -T postgres pg_restore --list < "${backup_file}" > /dev/null

cat > "${DEPLOY_STATE}" <<EOF
PREVIOUS_COMMIT=${previous_commit}
DATABASE_BACKUP=${backup_file}
EOF

echo "Получение ветки ${DEPLOY_BRANCH}..."
git fetch origin "${DEPLOY_BRANCH}"
git checkout "${DEPLOY_BRANCH}"
git merge --ff-only "origin/${DEPLOY_BRANCH}"

echo "Сборка Docker-образа..."
"${COMPOSE[@]}" build --pull breakfast_lecture_planner

echo "Проверка запуска Gunicorn в новом образе..."
docker run --rm --entrypoint python breakfast_lecture_planner -I \
    -c 'from gunicorn.workers.ggevent import GeventWorker'

echo "Запуск контейнеров..."
"${COMPOSE[@]}" up -d --remove-orphans

echo "Проверка и перезагрузка Nginx..."
"${COMPOSE[@]}" exec -T nginx nginx -t
"${COMPOSE[@]}" exec -T nginx nginx -s reload

echo "Проверка сайта ${HEALTHCHECK_URL}..."
for attempt in {1..30}; do
    container_id="$("${COMPOSE[@]}" ps -q breakfast_lecture_planner)"
    container_status="$(docker inspect --format '{{.State.Status}}' \
        "${container_id}" 2>/dev/null || true)"
    separator="?"
    [[ "${HEALTHCHECK_URL}" == *\?* ]] && separator="&"
    check_url="${HEALTHCHECK_URL}${separator}deploy_check=$(date +%s)"

    if [[ "${container_status}" == "running" ]] && \
        curl --fail --silent --show-error --location \
            --header "Cache-Control: no-cache" \
            --resolve "${HEALTHCHECK_RESOLVE}" \
            --max-time 10 "${check_url}" > /dev/null; then
        trap - ERR
        deployed_commit="$(git rev-parse HEAD)"
        cat >> "${DEPLOY_STATE}" <<EOF
DEPLOYED_COMMIT=${deployed_commit}
EOF
        echo "Деплой успешно завершён."
        echo "Резервная копия: ${backup_file}"
        exit 0
    fi

    if [[ "${attempt}" -lt 30 ]]; then
        sleep 2
    fi
done

echo "Сайт не прошёл проверку доступности." >&2
false
