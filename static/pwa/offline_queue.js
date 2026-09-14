(() => {
    'use strict';

    const DB_NAME = 'aegisshare-offline';
    const DB_VERSION = 1;
    const QUEUE_STORE = 'queue';
    const KEY_STORE = 'keys';
    const PAYLOAD_KEY_NAME = 'payload-aes-gcm-v1';
    const ALLOWED_STATUSES = new Set(['pending', 'syncing', 'synced', 'conflict', 'failed']);
    const encoder = new TextEncoder();
    const decoder = new TextDecoder();
    let encryptionKeyPromise = null;

    function assertSupported() {
        if (!window.indexedDB || !window.crypto?.subtle) {
            throw new Error('Armazenamento offline protegido indisponível neste navegador.');
        }
    }

    function requestAsPromise(request) {
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error || new Error('Falha no IndexedDB.'));
        });
    }

    function transactionDone(transaction) {
        return new Promise((resolve, reject) => {
            transaction.oncomplete = () => resolve();
            transaction.onerror = () => reject(transaction.error || new Error('Falha na transação IndexedDB.'));
            transaction.onabort = () => reject(transaction.error || new Error('Transação IndexedDB abortada.'));
        });
    }

    function openDatabase() {
        assertSupported();
        return new Promise((resolve, reject) => {
            const request = window.indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = () => {
                const db = request.result;
                if (!db.objectStoreNames.contains(QUEUE_STORE)) {
                    const queue = db.createObjectStore(QUEUE_STORE, { keyPath: 'idempotency_key' });
                    queue.createIndex('status', 'status', { unique: false });
                    queue.createIndex('created_at', 'created_at', { unique: false });
                }
                if (!db.objectStoreNames.contains(KEY_STORE)) {
                    db.createObjectStore(KEY_STORE, { keyPath: 'name' });
                }
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error || new Error('Não foi possível abrir o armazenamento offline.'));
            request.onblocked = () => reject(new Error('O armazenamento offline está bloqueado por outra aba.'));
        });
    }

    function bytesToBase64(bytes) {
        let binary = '';
        const chunkSize = 0x8000;
        for (let offset = 0; offset < bytes.length; offset += chunkSize) {
            binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
        }
        return btoa(binary);
    }

    function base64ToBytes(value) {
        const binary = atob(value);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) {
            bytes[index] = binary.charCodeAt(index);
        }
        return bytes;
    }

    async function readStoredEncryptionKey(db) {
        const transaction = db.transaction(KEY_STORE, 'readonly');
        const done = transactionDone(transaction);
        const existing = await requestAsPromise(
            transaction.objectStore(KEY_STORE).get(PAYLOAD_KEY_NAME)
        );
        await done;
        return existing?.key || null;
    }

    async function loadOrCreateEncryptionKey() {
        const db = await openDatabase();
        try {
            const existingKey = await readStoredEncryptionKey(db);
            if (existingKey) return existingKey;

            const key = await window.crypto.subtle.generateKey(
                { name: 'AES-GCM', length: 256 },
                false,
                ['encrypt', 'decrypt']
            );
            const writeTransaction = db.transaction(KEY_STORE, 'readwrite');
            const done = transactionDone(writeTransaction);
            const addRequest = writeTransaction.objectStore(KEY_STORE).add({
                name: PAYLOAD_KEY_NAME,
                key,
                created_at: new Date().toISOString(),
            });
            try {
                await requestAsPromise(addRequest);
                await done;
                return key;
            } catch (error) {
                await done.catch(() => {});
                if (error?.name !== 'ConstraintError') throw error;
                const winnerKey = await readStoredEncryptionKey(db);
                if (!winnerKey) throw error;
                return winnerKey;
            }
        } finally {
            db.close();
        }
    }

    function getEncryptionKey() {
        if (!encryptionKeyPromise) {
            encryptionKeyPromise = loadOrCreateEncryptionKey().catch((error) => {
                encryptionKeyPromise = null;
                throw error;
            });
        }
        return encryptionKeyPromise;
    }

    function validateText(value, label) {
        if (typeof value !== 'string' || !value.trim()) {
            throw new TypeError(`${label} é obrigatório.`);
        }
        return value.trim();
    }

    function generateIdempotencyKey() {
        assertSupported();
        if (typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
        const bytes = window.crypto.getRandomValues(new Uint8Array(16));
        return `offline-${bytesToBase64(bytes).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')}`;
    }

    function makeAdditionalData(record) {
        return encoder.encode([
            'aegisshare-offline-v1',
            record.idempotency_key,
            record.operation_type,
            record.user_session_fingerprint,
        ].join(':'));
    }

    async function enqueue({
        operationType,
        userSessionFingerprint,
        payload,
        idempotencyKey = null,
    }) {
        assertSupported();
        const operation_type = validateText(operationType, 'operationType');
        const user_session_fingerprint = validateText(
            userSessionFingerprint,
            'userSessionFingerprint'
        );
        const idempotency_key = validateText(
            idempotencyKey || generateIdempotencyKey(),
            'idempotencyKey'
        );
        if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
            throw new TypeError('payload deve ser um objeto.');
        }

        const record = {
            idempotency_key,
            operation_type,
            created_at: new Date().toISOString(),
            user_session_fingerprint,
            status: 'pending',
            retry_count: 0,
            crypto_version: 1,
        };
        const key = await getEncryptionKey();
        const iv = window.crypto.getRandomValues(new Uint8Array(12));
        const ciphertext = await window.crypto.subtle.encrypt(
            {
                name: 'AES-GCM',
                iv,
                additionalData: makeAdditionalData(record),
                tagLength: 128,
            },
            key,
            encoder.encode(JSON.stringify(payload))
        );
        record.payload_iv = bytesToBase64(iv);
        record.payload_ciphertext = bytesToBase64(new Uint8Array(ciphertext));

        const db = await openDatabase();
        try {
            const transaction = db.transaction(QUEUE_STORE, 'readwrite');
            const done = transactionDone(transaction);
            const addRequest = transaction.objectStore(QUEUE_STORE).add(record);
            await requestAsPromise(addRequest);
            await done;
        } finally {
            db.close();
        }
        return { ...record };
    }

    async function getRecord(idempotencyKey) {
        const idempotency_key = validateText(idempotencyKey, 'idempotencyKey');
        const db = await openDatabase();
        try {
            const transaction = db.transaction(QUEUE_STORE, 'readonly');
            const done = transactionDone(transaction);
            const record = await requestAsPromise(
                transaction.objectStore(QUEUE_STORE).get(idempotency_key)
            );
            await done;
            return record || null;
        } finally {
            db.close();
        }
    }

    async function readPayload(idempotencyKey) {
        const record = await getRecord(idempotencyKey);
        if (!record) return null;
        const key = await getEncryptionKey();
        const plaintext = await window.crypto.subtle.decrypt(
            {
                name: 'AES-GCM',
                iv: base64ToBytes(record.payload_iv),
                additionalData: makeAdditionalData(record),
                tagLength: 128,
            },
            key,
            base64ToBytes(record.payload_ciphertext)
        );
        return JSON.parse(decoder.decode(plaintext));
    }

    async function listMetadata({ status = null } = {}) {
        if (status !== null && !ALLOWED_STATUSES.has(status)) {
            throw new TypeError('status inválido.');
        }
        const db = await openDatabase();
        try {
            const transaction = db.transaction(QUEUE_STORE, 'readonly');
            const done = transactionDone(transaction);
            const records = await requestAsPromise(transaction.objectStore(QUEUE_STORE).getAll());
            await done;
            return records
                .filter((record) => status === null || record.status === status)
                .map((record) => ({
                    idempotency_key: record.idempotency_key,
                    operation_type: record.operation_type,
                    created_at: record.created_at,
                    user_session_fingerprint: record.user_session_fingerprint,
                    status: record.status,
                    retry_count: record.retry_count,
                    crypto_version: record.crypto_version,
                }));
        } finally {
            db.close();
        }
    }

    async function markStatus(idempotencyKey, status, { incrementRetry = false } = {}) {
        if (!ALLOWED_STATUSES.has(status)) throw new TypeError('status inválido.');
        const record = await getRecord(idempotencyKey);
        if (!record) return false;
        record.status = status;
        if (incrementRetry) record.retry_count += 1;

        const db = await openDatabase();
        try {
            const transaction = db.transaction(QUEUE_STORE, 'readwrite');
            const done = transactionDone(transaction);
            transaction.objectStore(QUEUE_STORE).put(record);
            await done;
        } finally {
            db.close();
        }
        return true;
    }

    async function remove(idempotencyKey) {
        const idempotency_key = validateText(idempotencyKey, 'idempotencyKey');
        const db = await openDatabase();
        try {
            const transaction = db.transaction(QUEUE_STORE, 'readwrite');
            const done = transactionDone(transaction);
            transaction.objectStore(QUEUE_STORE).delete(idempotency_key);
            await done;
        } finally {
            db.close();
        }
    }

    async function clear() {
        assertSupported();
        encryptionKeyPromise = null;
        await new Promise((resolve, reject) => {
            const request = window.indexedDB.deleteDatabase(DB_NAME);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error || new Error('Falha ao limpar dados offline.'));
            request.onblocked = () => reject(new Error('A limpeza offline foi bloqueada por outra aba.'));
        });
    }

    window.AegisOfflineQueue = Object.freeze({
        databaseName: DB_NAME,
        enqueue,
        readPayload,
        listMetadata,
        markStatus,
        remove,
        clear,
    });
})();
