// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Firebase Authentication for GMATWiz (email/password), shared by desktop and
// mobile since both render this same SvelteKit app. The sign-in gate only turns
// on once firebaseConfig has a real apiKey; until then `authEnabled` is false and
// the app runs without auth.

import { initializeApp, type FirebaseApp } from "firebase/app";
import {
    createUserWithEmailAndPassword,
    getAuth,
    onAuthStateChanged,
    signInWithEmailAndPassword,
    signOut,
    type Auth,
    type User,
} from "firebase/auth";

import { firebaseConfig } from "./firebaseConfig";

export const authEnabled = Boolean(firebaseConfig.apiKey);

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
if (authEnabled) {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
}

export interface AuthUser {
    uid: string;
    email: string | null;
}

function toAuthUser(u: User | null): AuthUser | null {
    return u ? { uid: u.uid, email: u.email } : null;
}

/** Subscribe to sign-in state. Fires immediately with the current user (or null),
 * then on every change. Returns an unsubscribe function. */
export function onUser(cb: (user: AuthUser | null) => void): () => void {
    if (!auth) {
        cb(null);
        return () => {};
    }
    return onAuthStateChanged(auth, (u) => cb(toAuthUser(u)));
}

/** Turn a Firebase auth error into a short, human message. */
function authMessage(err: unknown): string {
    const code = (err as { code?: string })?.code ?? "";
    switch (code) {
        case "auth/invalid-email":
            return "That email doesn't look right.";
        case "auth/missing-password":
            return "Enter a password.";
        case "auth/weak-password":
            return "Password must be at least 6 characters.";
        case "auth/email-already-in-use":
            return "An account with that email already exists.";
        case "auth/invalid-credential":
        case "auth/wrong-password":
        case "auth/user-not-found":
            return "Email or password is incorrect.";
        case "auth/network-request-failed":
            return "Network error. Check your connection.";
        default:
            return (err as { message?: string })?.message ?? "Something went wrong.";
    }
}

export async function signIn(email: string, password: string): Promise<void> {
    if (!auth) throw new Error("Auth is not configured.");
    try {
        await signInWithEmailAndPassword(auth, email.trim(), password);
    } catch (err) {
        throw new Error(authMessage(err));
    }
}

export async function signUp(email: string, password: string): Promise<void> {
    if (!auth) throw new Error("Auth is not configured.");
    try {
        await createUserWithEmailAndPassword(auth, email.trim(), password);
    } catch (err) {
        throw new Error(authMessage(err));
    }
}

export async function signOutUser(): Promise<void> {
    if (auth) await signOut(auth);
}
