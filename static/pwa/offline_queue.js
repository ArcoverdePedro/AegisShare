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
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);
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

    async function loadOrCreateEncryptionKey() {
        const db = await openDatabase();
        try {
            const readTransaction = db.transaction(KEY_STORE, 'readonly');
            const existing = await requestAsPromise(
                readTransaction.objectStore(KEY_STORE).get(PAYLOAD_KEY_NAME)
            );
            await transactionDone(readTransaction);
            if (existing?.key) return existing.key;

            const key = await crypto.subtle.generateKey(
                { name: 'AES-GCM', length: 256 },
                false,
                ['encrypt', 'decrypt']
            );
            const writeTransaction = db.transaction(KEY_STORE, 'readwrite');
            writeTransaction.objectStore(KEY_STORE).put({
                name: PAYLOAD_KEY_NAME,
                key,
                created_at: new Date().toISOString(),
            });
            await transactionDone(writeTransaction);
            return key;
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
        idempotencyKey = crypto.randomUUID(),
    }) {
        if (!crypto?.subtle || !indexedDB) {
            throw new Error('Armazenamento offline protegido indisponível neste navegador.');
        }
        const operation_type = validateText(operationType, 'operationType');
        const user_session_fingerprint = validateText(
            userSessionFingerprint,
            'userSessionFingerprint'
        );
        const idempotency_key = validateText(idempotencyKey, 'idempotencyKey');
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
        const iv = crypto.getRandomValues(new Uint8Array(12));
        const ciphertext = await crypto.subtle.encrypt(
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
            transaction.objectStore(QUEUE_STORE).add(record);
            await transactionDone(transaction);
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
            const record = await requestAsPromise(
                transaction.objectStore(QUEUE_STORE).get(idempotency_key)
            );
            await transactionDone(transaction);
            return record || null;
        } finally {
            db.close();
        }
    }

    async function readPayload(idempotencyKey) {
        const record = await getRecord(idempotencyKey);
        if (!record) return null;
        const key = await getEncryptionKey();
        const plaintext = await crypto.subtle.decrypt(
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
            const records = await requestAsPromise(transaction.objectStore(QUEUE_STORE).getAll());
            await transactionDone(transaction);
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
            transaction.objectStore(QUEUE_STORE).put(record);
            await transactionDone(transaction);
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
            transaction.objectStore(QUEUE_STORE).delete(idempotency_key);
            await transactionDone(transaction);
        } finally {
            db.close();
        }
    }

    async function clear() {
        encryptionKeyPromise = null;
        await new Promise((resolve, reject) => {
            const request = indexedDB.deleteDatabase(DB_NAME);
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
