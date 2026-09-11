(() => {
    const status = document.getElementById('pwaConnectionStatus');

    const renderConnectivity = () => {
        if (!status) return;
        const offline = !navigator.onLine;
        status.hidden = !offline;
        status.setAttribute('aria-hidden', offline ? 'false' : 'true');
    };

    window.addEventListener('online', renderConnectivity);
    window.addEventListener('offline', renderConnectivity);
    renderConnectivity();

    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/service-worker.js', { scope: '/' }).catch(() => {
                // O site continua funcional sem PWA; não exponha dados no console.
            });
        });

        document.addEventListener('submit', (event) => {
            const form = event.target;
            if (!(form instanceof HTMLFormElement) || !form.matches('[data-pwa-logout]')) return;
            navigator.serviceWorker.controller?.postMessage({ type: 'CLEAR_LOCAL_DATA' });
        });
    }
})();
