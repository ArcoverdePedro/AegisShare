#!/usr/bin/env bash
# Backup cifrado (banco + arquivos) da stack Compose. Uso: scripts/backup.sh <diretorio-destino>
# Exige BACKUP_ENCRYPTION_KEY no .env. FILE_ENCRYPTION_KEY e BACKUP_ENCRYPTION_KEY NAO entram no
# backup: guarde-as em cofre separado, senao a restauracao nao decifra nada.
set -euo pipefail

dest="${1:?informe o diretorio de destino}"
compose=(docker compose ${COMPOSE_FILE_ARGS:-})
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
umask 077
mkdir -p "$dest"

"${compose[@]}" exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | "${compose[@]}" exec -T aegis_share python manage.py backup_seal \
  > "$dest/db-$stamp.dump.aegisbak.partial"
"${compose[@]}" exec -T aegis_share tar -C /app -cf - private_files \
  | "${compose[@]}" exec -T aegis_share python manage.py backup_seal \
  > "$dest/files-$stamp.tar.aegisbak.partial"

# Confere autenticacao completa antes de considerar o backup valido.
for part in "$dest"/*-"$stamp".*.partial; do
  "${compose[@]}" exec -T aegis_share python manage.py backup_open < "$part" > /dev/null
  mv "$part" "${part%.partial}"
done
sha256sum "$dest"/*-"$stamp".*.aegisbak > "$dest/SHA256SUMS-$stamp"
echo "backup ok: $dest ($stamp)"
