(() => {
    'use strict';

    const root = document.getElementById('webPushControls');
    if (!root) return;

    const enableButton = root.querySelector('[data-push-enable]');
    const disableButton = root.querySelector('[data-push-disable]');
    const status = root.querySelector('[data-push-status]');
    const csrfToken = root.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
    const configUrl = root.dataset.configUrl;
    const subscribeUrl = root.dataset.subscribeUrl;
    const unsubscribeUrl = root.dataset.unsubscribeUrl;

    const setStatus = (message, tone = 'info') => {
        if (!status) return;
        status.textContent = message;
        status.className = `help is-${tone}`;
    };

    const setButtons = ({ subscribed = false, disabled = false } = {}) => {
        if (enableButton) {
            enableButton.hidden = subscribed || disabled;
            enableButton.disabled = disabled;
        }
        if (disableButton) {
            disableButton.hidden = !subscribed || disabled;
            disableButton.disabled = disabled;
        }
    };

    const base64UrlToUint8Array = (value) => {
        const padding = '='.repeat((4 - (value.length % 4)) % 4);
        const base64 = (value + padding).replace(/-/g, '+').replace(/_/g, '/');
        const raw = atob(base64);
        return Uint8Array.from(raw, (char) => char.charCodeAt(0));
    };

    const postJson = async (url, payload) => {
        const response = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    };

    const getRegistration = async () => {
        if (!('serviceWorker' in navigator)) throw new Error('service_worker_unsupported');
        return navigator.serviceWorker.ready;
    };

    const registerSubscription = async (subscription) => {
        const serialized = subscription.toJSON();
        if (!serialized.endpoint || !serialized.keys?.p256dh || !serialized.keys?.auth) {
            throw new Error('invalid_subscription');
        }
        await postJson(subscribeUrl, serialized);
    };

    const loadConfig = async () => {
        const response = await fetch(configUrl, {
            credentials: 'same-origin',
            cache: 'no-store',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    };

    const refresh = async () => {
        if (!('Notification' in window) || !('PushManager' in window)) {
            setButtons({ disabled: true });
            setStatus('Este navegador não oferece Web Push compatível.', 'warning');
            return null;
        }

        const config = await loadConfig();
        if (!config.enabled || !config.public_key) {
            setButtons({ disabled: true });
            setStatus('Web Push ainda não foi habilitado pelo administrador.', 'info');
            return null;
        }

        const registration = await getRegistration();
        const subscription = await registration.pushManager.getSubscription();
        if (subscription) {
            // Revalida o vínculo com a sessão atual sem transportar conteúdo sensível.
            await registerSubscription(subscription);
            setButtons({ subscribed: true });
            setStatus('Notificações deste dispositivo estão ativadas.', 'success');
        } else if (Notification.permission === 'denied') {
            setButtons({ disabled: true });
            setStatus('Notificações foram bloqueadas nas permissões do navegador.', 'warning');
        } else {
            setButtons({ subscribed: false });
            setStatus('Ative notificações genéricas para saber quando houver novidades.', 'info');
        }
        return { config, registration, subscription };
    };

    enableButton?.addEventListener('click', async () => {
        enableButton.disabled = true;
        try {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                setStatus('Permissão de notificações não concedida.', 'warning');
                return;
            }
            const config = await loadConfig();
            if (!config.enabled || !config.public_key) throw new Error('webpush_disabled');
            const registration = await getRegistration();
            let subscription = await registration.pushManager.getSubscription();
            if (!subscription) {
                subscription = await registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: base64UrlToUint8Array(config.public_key),
                });
            }
            await registerSubscription(subscription);
            setButtons({ subscribed: true });
            setStatus('Notificações deste dispositivo foram ativadas.', 'success');
        } catch (_error) {
            setButtons({ subscribed: false });
            setStatus('Não foi possível ativar Web Push neste dispositivo.', 'danger');
        } finally {
            enableButton.disabled = false;
        }
    });

    disableButton?.addEventListener('click', async () => {
        disableButton.disabled = true;
        try {
            const registration = await getRegistration();
            const subscription = await registration.pushManager.getSubscription();
            if (subscription) {
                try {
                    await postJson(unsubscribeUrl, { endpoint: subscription.endpoint });
                } finally {
                    await subscription.unsubscribe();
                }
            }
            setButtons({ subscribed: false });
            setStatus('Notificações deste dispositivo foram desativadas.', 'info');
        } catch (_error) {
            setStatus('Não foi possível desativar Web Push agora.', 'danger');
        } finally {
            disableButton.disabled = false;
        }
    });

    refresh().catch(() => {
        setButtons({ disabled: true });
        setStatus('Não foi possível consultar a configuração de Web Push.', 'warning');
    });
})();
