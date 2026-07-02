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

/** On login: apply the account's stored state, or reset to a fresh start for a
 * brand-new account (so it begins at the diagnostic). Returns whether it's new. */
export async function pullAccountState(uid: string): Promise<{ isNew: boolean }> {
    if (!provider) return { isNew: false };
    const remote = await provider.load(uid);
    if (remote) {
        await importState(remote);
        return { isNew: false };
    }
    await resetState();
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
        await provider.save(uid, stripEmpty(await exportState()));
    } catch (e) {
        console.error("GMATWiz state push failed", e);
    }
}
