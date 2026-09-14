# ADR-0007 — Web Push direto com pywebpush

## Status
Aceito para a Spec 014 em 2026-09-14.

## Contexto

A Spec 014 exige notificações Web Push genéricas, sem PHI, e o AegisShare roda em Python 3.14/Django moderno. A fundação PWA já serve manifest, service worker e fallback diretamente pelo monólito, portanto adicionar um wrapper Django apenas para Push aumentaria acoplamento sem benefício funcional.

Na validação de compatibilidade, `pywebpush` 2.5.0 oferece suporte a Python >= 3.10, Web Push/VAPID e tratamento dos códigos HTTP dos provedores. O wrapper `django-webpush` não é necessário para a arquitetura atual.

## Decisão

- usar `pywebpush >= 2.5,<3` como biblioteca de publicação;
- manter subscriptions em `apps.pwa.PushSubscription` vinculadas ao usuário autenticado;
- usar sessão Django + CSRF para registrar/revogar subscriptions;
- enviar Push **sem payload de aplicação** (`data=None`);
- fixar título, corpo e destino genéricos no service worker;
- desativar subscriptions quando o provedor responder 404/410;
- manter VAPID privado somente em variável de ambiente/secret manager;
- não registrar endpoint, chaves de subscription ou conteúdo de notificações em logs.

## Consequências

- o sistema não depende de `django-webpush` nem de API REST pública;
- Web Push fica desabilitado de forma segura enquanto o trio VAPID não estiver configurado;
- o envio inicial é síncrono após commit da notificação; quando Celery estiver disponível, o mesmo serviço poderá ser deslocado para job assíncrono sem alterar o contrato do navegador;
- a rotação de VAPID exige renovação das subscriptions existentes.

## Segurança

O provedor externo recebe apenas o protocolo Web Push e nenhum título, corpo, nome de paciente, diagnóstico, documento ou identificador clínico. Ao clicar, o usuário abre `/notificacoes/`, que continua sujeito à autenticação e autorização do monólito.
