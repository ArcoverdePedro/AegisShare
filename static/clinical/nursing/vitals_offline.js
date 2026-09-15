(() => {
    'use strict';

    const form = document.querySelector('[data-nursing-vitals-offline]');
    if (!form || !window.AegisOfflineQueue) return;

    const OPERATION_TYPE = 'nursing.vitals.record';
    const MEASURE_FIELDS = [
        'temperature_c',
        'heart_rate_bpm',
        'respiratory_rate_irpm',
        'systolic_bp_mmhg',
        'diastolic_bp_mmhg',
        'oxygen_saturation_pct',
        'weight_kg',
    ];
    const queue = window.AegisOfflineQueue;
    const status = form.querySelector('[data-offline-status]');
    const syncUrl = form.dataset.syncUrl;
    const sessionFingerprint = form.dataset.sessionFingerprint;
    const encounterId = form.dataset.encounterId;
    const replacesId = form.dataset.replacesId || null;
    const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
    let syncing = false;

    const setStatus = (message, tone = 'info') => {
        if (!status) return;
        status.textContent = message;
        status.className = `notification is-${tone} is-light`;
        status.hidden = false;
    };

    const buildPayload = () => {
        const measurements = {};
        for (const fieldName of MEASURE_FIELDS) {
            const field = form.elements.namedItem(fieldName);
            const value = typeof field?.value === 'string' ? field.value.trim() : '';
            if (value) measurements[fieldName] = value;
        }
        return {
            encounter_id: encounterId,
            recorded_at: form.elements.namedItem('recorded_at')?.value || '',
            replaces_id: replacesId,
            measurements,
        };
    };

    const markConflict = async (idempotencyKey) => {
        await queue.markStatus(idempotencyKey, 'conflict').catch(() => {});
    };

    const syncRecord = async (metadata) => {
        if (metadata.user_session_fingerprint !== sessionFingerprint) {
            await markConflict(metadata.idempotency_key);
            return 'conflict';
        }

        let payload;
        try {
            payload = await queue.readPayload(metadata.idempotency_key);
        } catch (_error) {
            await markConflict(metadata.idempotency_key);
            return 'conflict';
        }
        if (!payload) return 'conflict';

        await queue.markStatus(metadata.idempotency_key, 'syncing');
        try {
            const response = await fetch(syncUrl, {
                method: 'POST',
                credentials: 'same-origin',
                cache: 'no-store',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({
                    idempotency_key: metadata.idempotency_key,
                    operation_type: metadata.operation_type,
                    user_session_fingerprint: metadata.user_session_fingerprint,
                    payload,
                }),
            });

            if (response.redirected) {
                await markConflict(metadata.idempotency_key);
                return 'conflict';
            }

            const contentType = response.headers.get('content-type') || '';
            const result = contentType.includes('application/json')
                ? await response.json().catch(() => null)
                : null;

            if (response.ok && result?.status === 'synced') {
                await queue.markStatus(metadata.idempotency_key, 'synced');
                await queue.remove(metadata.idempotency_key);
                return 'synced';
            }

            if ([400, 403, 409].includes(response.status)) {
                await markConflict(metadata.idempotency_key);
                return 'conflict';
            }

            await queue.markStatus(metadata.idempotency_key, 'pending', {
                incrementRetry: true,
            });
            return 'pending';
        } catch (_error) {
            await queue.markStatus(metadata.idempotency_key, 'pending', {
                incrementRetry: true,
            }).catch(() => {});
            return 'pending';
        }
    };

    const syncPending = async () => {
        if (syncing || !navigator.onLine) return;
        syncing = true;
        try {
            const metadata = (await queue.listMetadata()).filter(
                (item) =>
                    item.operation_type === OPERATION_TYPE
                    && (item.status === 'pending' || item.status === 'syncing')
            );
            if (!metadata.length) return;

            let syncedCount = 0;
            let conflictCount = 0;
            let pendingCount = 0;
            for (const item of metadata) {
                const outcome = await syncRecord(item);
                if (outcome === 'synced') syncedCount += 1;
                if (outcome === 'conflict') conflictCount += 1;
                if (outcome === 'pending') pendingCount += 1;
            }

            if (conflictCount) {
                setStatus(
                    `${conflictCount} registro(s) offline exigem revisão antes de nova tentativa.`,
                    'warning'
                );
            } else if (pendingCount) {
                setStatus(
                    `${pendingCount} registro(s) continuam pendentes de sincronização.`,
                    'info'
                );
            } else if (syncedCount) {
                setStatus(
                    `${syncedCount} registro(s) offline foram confirmados no prontuário.`,
                    'success'
                );
            }
        } finally {
            syncing = false;
        }
    };

    form.addEventListener('submit', async (event) => {
        if (navigator.onLine) return;
        event.preventDefault();

        if (!form.reportValidity()) return;
        const payload = buildPayload();
        if (!Object.keys(payload.measurements).length) {
            setStatus('Informe ao menos uma medida clínica antes de salvar offline.', 'danger');
            return;
        }

        try {
            await queue.enqueue({
                operationType: OPERATION_TYPE,
                userSessionFingerprint: sessionFingerprint,
                payload,
            });
            setStatus(
                'Registro salvo de forma cifrada neste dispositivo. Ainda não foi confirmado no prontuário.',
                'warning'
            );
        } catch (_error) {
            setStatus(
                'Não foi possível proteger o registro offline neste dispositivo.',
                'danger'
            );
        }
    });

    window.addEventListener('online', () => {
        syncPending();
    });

    if (navigator.onLine) syncPending();
})();
