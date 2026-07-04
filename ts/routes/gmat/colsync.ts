// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Whole-collection sync via Firebase Cloud Storage. This is an ADDITIONAL layer
// on top of the Firestore config sync in sync.ts: where that keeps the GMATWiz
// config JSON (plan/progress/scores/errors/quizzes) in sync, this keeps the
// ENTIRE collection FILE (cards + revlog = the full SRS state) in sync, so
// desktop and mobile share one complete schedule.
//
// Safety is paramount:
//   - Last-writer-wins by the collection's OWN modification time (Anki col.mod),
//     stored on every upload in the object's customMetadata.col_mod.
//   - We ALWAYS back up the copy we are about to overwrite before replacing it:
//     the desktop backs up the local file locally before a download-replace, and
//     before overwriting the cloud object we first copy it to a backups/ path.
//   - Every Storage/network call is guarded: on failure we log and continue, so
//     a sync hiccup can never break the app. Everything only runs when signed in.

import { getApps } from "firebase/app";
import {
    getBytes,
    getMetadata,
    getStorage,
    ref,
    uploadBytes,
    type StorageReference,
} from "firebase/storage";

import { colExport, colMeta, colReplace, refreshOverview } from "./api";
import { authEnabled } from "./auth";

const CONTENT_TYPE = "application/octet-stream";

// Which account's data the LOCAL collection file currently holds. Used to detect
// an account SWITCH on login: the local file belongs to the PREVIOUS account, so
// last-writer-wins by col.mod is meaningless (it would upload the old account's
// collection over the new account's cloud copy). Persisted so it survives reloads.
const COL_OWNER_KEY = "gmatwiz.colOwner";

/** The uid the local collection currently belongs to, or null if unknown. */
export function getColOwner(): string | null {
    try {
        return typeof localStorage !== "undefined" ? localStorage.getItem(COL_OWNER_KEY) : null;
    } catch {
        return null;
    }
}

function setColOwner(uid: string): void {
    try {
        if (typeof localStorage !== "undefined") localStorage.setItem(COL_OWNER_KEY, uid);
    } catch {
        /* localStorage unavailable (private mode / SSR) - owner tracking degrades. */
    }
}

/** Mark the local collection as belonging to this account WITHOUT touching the
 * cloud - used when a brand-new account resets locally and must not inherit (or
 * download) any leftover/stale collection. */
export function claimCollectionOwner(uid: string): void {
    setColOwner(uid);
}

/** How the collection landed on login - lets the caller decide the config step. */
export type ColLanding = "downloaded" | "seeded" | "uploaded" | "empty" | "skipped";

/** Path of the account's live collection object. */
function collectionPath(uid: string): string {
    return `users/${uid}/collection.anki2`;
}

/** Path of a timestamped backup of a cloud copy we're about to overwrite. */
function backupPath(uid: string, mod: number): string {
    return `users/${uid}/backups/collection-${mod}.anki2`;
}

/** A Storage ref, or null when auth/Storage isn't available (app runs without
 * sync then). Never throws. */
function storageRef(path: string): StorageReference | null {
    if (!authEnabled || !getApps().length) return null;
    try {
        return ref(getStorage(getApps()[0]), path);
    } catch (e) {
        console.error("GMATWiz colsync: storage unavailable", e);
        return null;
    }
}

// ---- base64 <-> bytes (browser; no Node Buffer) ----
// Chunked so multi-MB collection files don't blow the call stack via a single
// String.fromCharCode(...bigArray) / apply.

const CHUNK = 0x8000; // 32 KiB of bytes per fromCharCode call

function bytesToBase64(bytes: Uint8Array): string {
    let binary = "";
    for (let i = 0; i < bytes.length; i += CHUNK) {
        binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
    }
    return btoa(binary);
}

function base64ToBytes(b64: string): Uint8Array {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
}

/** Read the col_mod stored on a Storage object. Returns null when the object
 * doesn't exist yet; rethrows other errors so callers don't mistake a transient
 * failure for "no cloud copy" and clobber it. */
async function readRemoteMod(r: StorageReference): Promise<number | null> {
    try {
        const meta = await getMetadata(r);
        const raw = meta.customMetadata?.col_mod;
        const n = raw != null ? Number(raw) : NaN;
        // Object exists but has no/garbled clock -> treat as the oldest possible
        // so the local copy wins (and the cloud copy still gets backed up first).
        return Number.isFinite(n) ? n : 0;
    } catch (e) {
        if ((e as { code?: string })?.code === "storage/object-not-found") {
            return null;
        }
        throw e;
    }
}

/** Upload this device's collection as the account's live object, stamping its
 * col.mod into customMetadata.col_mod. Best-effort: logs and returns on failure. */
export async function uploadCollection(uid: string): Promise<void> {
    const r = storageRef(collectionPath(uid));
    if (!r) return;
    try {
        // SAFETY: never push a plan-less (blank / freshly-reset) local collection
        // OVER an account that already has a cloud copy - that would erase real
        // progress. A blank local has nothing worth syncing anyway. (It may still
        // seed the cloud when none exists yet.)
        const ov = await refreshOverview();
        if (!ov || !ov.plan) {
            const remoteMod = await readRemoteMod(r);
            if (remoteMod !== null) return;
        }
        const { mod } = await colMeta();
        const { b64 } = await colExport();
        if (!b64) return;
        const bytes = base64ToBytes(b64);
        await uploadBytes(r, bytes, {
            contentType: CONTENT_TYPE,
            customMetadata: { col_mod: String(mod) },
        });
    } catch (e) {
        console.error("GMATWiz colsync: upload failed", e);
    }
}

/** Copy the current cloud object to a timestamped backup before we overwrite it,
 * so an overwritten cloud copy is always recoverable. Best-effort. */
async function backupRemote(uid: string, current: StorageReference, remoteMod: number): Promise<void> {
    const backup = storageRef(backupPath(uid, remoteMod));
    if (!backup) return;
    try {
        const buf = await getBytes(current);
        await uploadBytes(backup, new Uint8Array(buf), {
            contentType: CONTENT_TYPE,
            customMetadata: { col_mod: String(remoteMod) },
        });
    } catch (e) {
        console.error("GMATWiz colsync: remote backup failed", e);
    }
}

/**
 * Reconcile this device's collection with the account's cloud copy on login.
 * Never throws; returns how the collection landed so the caller can pick the
 * right config step.
 *
 * ACCOUNT SWITCH (opts.switching): the local file belongs to the PREVIOUS
 * account, so last-writer-wins by col.mod is wrong (the local file is "newer"
 * and would clobber the new account's cloud data). Instead the new account's
 * cloud copy is AUTHORITATIVE:
 *   - cloud copy exists -> download + replace locally ("downloaded").
 *   - no cloud copy     -> the account has no collection on any device yet; do
 *                          NOT upload the previous account's file over it. Return
 *                          "empty" so the caller resets / imports config cleanly.
 *
 * SAME ACCOUNT (default): last-writer-wins by col.mod, as before:
 *   - no cloud copy yet     -> seed it from this device ("seeded").
 *   - cloud is newer        -> download + replace locally ("downloaded").
 *   - local is newer/equal  -> back up the cloud copy, then upload ("uploaded").
 */
export async function pullCollectionOnLogin(
    uid: string,
    opts: { switching?: boolean } = {},
): Promise<{ landed: ColLanding }> {
    const r = storageRef(collectionPath(uid));
    if (!r) return { landed: "skipped" };
    try {
        const remoteMod = await readRemoteMod(r);

        if (opts.switching) {
            if (remoteMod === null) {
                // New account on this device with no cloud collection. Claim
                // ownership but leave the cloud empty until it creates its own
                // data - the caller resets local state for a clean start.
                setColOwner(uid);
                return { landed: "empty" };
            }
            const buf = await getBytes(r);
            const b64 = bytesToBase64(new Uint8Array(buf));
            const res = await colReplace(b64);
            if (res.ok) {
                setColOwner(uid);
                await refreshOverview();
                return { landed: "downloaded" };
            }
            return { landed: "skipped" };
        }

        const { mod: localMod } = await colMeta();

        if (remoteMod === null) {
            await uploadCollection(uid); // first device seeds the cloud
            setColOwner(uid);
            return { landed: "seeded" };
        }

        if (remoteMod > localMod) {
            const buf = await getBytes(r);
            const b64 = bytesToBase64(new Uint8Array(buf));
            const res = await colReplace(b64);
            if (res.ok) {
                setColOwner(uid);
                await refreshOverview();
                return { landed: "downloaded" };
            }
            return { landed: "skipped" };
        }

        // We're about to overwrite the cloud copy: preserve it first.
        await backupRemote(uid, r, remoteMod);
        await uploadCollection(uid);
        setColOwner(uid);
        return { landed: "uploaded" };
    } catch (e) {
        console.error("GMATWiz colsync: login pull failed", e);
        return { landed: "skipped" };
    }
}

// Debounced upload, used on sign-out / page-hide so rapid fire-and-forget
// triggers coalesce into a single upload.
let uploadTimer: ReturnType<typeof setTimeout> | null = null;

export function scheduleCollectionUpload(uid: string, delayMs = 1500): void {
    if (!authEnabled) return;
    if (uploadTimer) clearTimeout(uploadTimer);
    uploadTimer = setTimeout(() => {
        uploadTimer = null;
        void uploadCollection(uid);
    }, delayMs);
}
