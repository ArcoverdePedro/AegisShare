# Contrato — Web Push sem PHI

## Objetivo

Permitir aviso em segundo plano sem transportar dados clínicos identificáveis nem expor conteúdo de notificações internas ao provedor de Push.

## Registro da subscription

Rotas internas autenticadas por sessão Django e protegidas por CSRF:

- `GET /pwa/push/config/` — informa se Push está configurado e expõe somente a chave VAPID pública;
- `POST /pwa/push/subscribe/` — registra `endpoint`, `keys.p256dh` e `keys.auth` da `PushSubscription` do navegador;
- `POST /pwa/push/unsubscribe/` — desativa a subscription pertencente ao usuário atual.

O endpoint deve ser HTTPS. O servidor armazena um SHA-256 do endpoint para unicidade e um SHA-256 da chave de sessão para vincular a subscription à sessão autenticada sem persistir a chave de sessão em claro. Endpoint, chaves e fingerprint nunca são escritos nos logs de aplicação.

Ao fazer logout, somente subscriptions ligadas àquela sessão são desativadas; subscriptions de outros dispositivos/sessões permanecem ativas. `Clear-Site-Data` continua limpando cache/storage locais.

## Payload

O servidor publica com `data=None`. Nenhum dos campos abaixo pode ser enviado ao provedor Web Push:

- nome ou identificador de paciente;
- diagnóstico, medicamento, sinais vitais ou conteúdo de evolução;
- nome de arquivo/documento;
- título/corpo da `Notification` interna;
- identificadores de prontuário ou encontro.

O service worker fixa localmente:

- título: `AegisShare`;
- corpo: `Você tem uma nova notificação.`;
- destino: `/notificacoes/`.

Ao abrir o destino, sessão e autorização são revalidadas pelo Django.

## VAPID

Configuração obrigatoriamente em trio:

- `WEBPUSH_VAPID_PUBLIC_KEY`;
- `WEBPUSH_VAPID_PRIVATE_KEY`;
- `WEBPUSH_VAPID_SUBJECT` (`mailto:` ou `https://`).

Se o trio não estiver presente, Web Push permanece desabilitado. A chave privada não pode ser enviada ao navegador, versionada ou escrita em logs.

## Entrega e falhas

- timeout de envio configurável por `WEBPUSH_SEND_TIMEOUT_SECONDS`;
- TTL curto de 300 segundos;
- respostas 404/410 desativam a subscription expirada;
- outras falhas incrementam contador técnico sem apagar automaticamente a subscription;
- falhas de Push não podem impedir a criação da notificação interna.

## Testes obrigatórios

- chave privada VAPID nunca aparece na resposta de configuração;
- inscrição exige autenticação, CSRF e endpoint HTTPS;
- vínculo de sessão é persistido somente como hash;
- logout desativa apenas a subscription vinculada à sessão encerrada;
- remetente usa `data=None`;
- service worker não lê `event.data` e usa cópia genérica fixa;
- 404/410 desativam a subscription;
- testes anteriores de cache/IndexedDB continuam garantindo ausência de PHI local em texto claro.
