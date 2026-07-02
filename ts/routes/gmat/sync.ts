// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Cross-device account sync. On login we load the signed-in user's GMATWiz state
// (plan, progress, mocks, official scores, error log, ... = the collection's
// config JSON) and apply it locally; on changes we push it back. Keyed by the
// Firebase uid so logging into an account loads that account's data on any device.
//
// This is deliberately written behind a small SyncProvider interface: today it's
// backed by Firestore (free, no server, safe - no whole-collection file swap);
// swapping in a Cloud Storage provider later (full-collection sync) only means
// adding another provider, not changing this orchestration or the app.

import { getApps } from "firebase/app";
import { doc, getDoc, getFirestore, setDoc, type Firestore } from "firebase/firestore";

import { exportState, importState, resetState, type GmatState } from "./api";
import { authEnabled } from "./auth";

interface SyncProvider {
    /** The stored state for this account, or null if the account is brand new. */
    load(uid: string): Promise<GmatState | null>;
    /** Persist this account's state. */
    save(uid: string, state: GmatState): Promise<void>;
}

class FirestoreProvider implements SyncProvider {
    private db: Firestore;
    constructor(db: Firestore) {
        this.db = db;
    }
    async load(uid: string): Promise<GmatState | null> {
        const snap = await getDoc(doc(this.db, "users", uid));
        return snap.exists() ? (snap.data() as GmatState) : null;
    }
    async save(uid: string, state: GmatState): Promise<void> {
        await setDoc(doc(this.db, "users", uid), state);
    }
}

const provider: SyncProvider | null =
    authEnabled && getApps().length ? new FirestoreProvider(getFirestore(getApps()[0])) : null;

/** Firestore rejects undefined; drop null/undefined so absent keys stay absent. */
function stripEmpty(state: GmatState): GmatState {
    const out: GmatState = {};
    for (const [k, v] of Object.entries(state)) {
        if (v !== null && v !== undefined) out[k] = v;
    }
    return out;
}

// Timestamp (ms) of the newest state this device has written or applied. The
// auto-sync poll only pulls genuinely newer remote state (last-writer-wins) and
// never re-applies its own push, so two devices don't ping-pong each other.
let lastSyncedAt = 0;

function stampOf(state: GmatState | null): number {
    const v = state?.updatedAt;
    return typeof v === "number" ? v : 0;
}

/** On login: apply the account's stored state, or reset to a fresh start for a
 * brand-new account (so it begins at the diagnostic). Returns whether it's new. */
export async function pullAccountState(uid: string): Promise<{ isNew: boolean }> {
    if (!provider) return { isNew: false };
    const remote = await provider.load(uid);
    if (remote) {
        await importState(remote);
        lastSyncedAt = stampOf(remote) || Date.now();
        return { isNew: false };
    }
    await resetState();
    lastSyncedAt = 0;
    return { isNew: true };
}

let pushTimer: ReturnType<typeof setTimeout> | null = null;

/** Debounced upload of this device's state to the account (call after mutations). */
export function scheduleStatePush(uid: string): void {
    if (!provider) return;
    if (pushTimer) clearTimeout(pushTimer);
    pushTimer = setTimeout(() => void pushStateNow(uid), 1500);
}

export async function pushStateNow(uid: string): Promise<void> {
    if (!provider) return;
    try {
        const updatedAt = Date.now();
        await provider.save(uid, { ...stripEmpty(await exportState()), updatedAt });
        lastSyncedAt = updatedAt;
    } catch (e) {
        console.error("GMATWiz state push failed", e);
    }
}

let autoTimer: ReturnType<typeof setInterval> | null = null;

/** Keep this device in sync automatically (no manual button): poll the account
 * doc and apply any genuinely newer state written by another device. Pushes
 * still happen on local change (scheduleStatePush). Returns a stop function. */
export function startAutoSync(
    uid: string,
    onRemoteApplied: () => void,
    intervalMs = 12000,
): () => void {
    if (!provider) return () => {};
    stopAutoSync();
    autoTimer = setInterval(() => void pullIfChanged(uid, onRemoteApplied), intervalMs);
    return stopAutoSync;
}

export function stopAutoSync(): void {
    if (autoTimer) {
        clearInterval(autoTimer);
        autoTimer = null;
    }
}

async function pullIfChanged(uid: string, onRemoteApplied: () => void): Promise<void> {
    if (!provider) return;
    try {
        const remote = await provider.load(uid);
        const remoteAt = stampOf(remote);
        if (remote && remoteAt > lastSyncedAt) {
            await importState(remote);
            lastSyncedAt = remoteAt;
            onRemoteApplied();
        }
    } catch (e) {
        console.error("GMATWiz auto-sync pull failed", e);
    }
}
