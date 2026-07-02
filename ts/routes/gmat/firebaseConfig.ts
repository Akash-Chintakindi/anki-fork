// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Firebase web config for GMATWiz sign-in. Fill these from the Firebase console
// (Project settings -> your Web app -> "SDK setup and configuration" -> Config).
// These values are NOT secret and are safe to commit/ship in a client app.
//
// While `apiKey` is empty the sign-in gate is DISABLED and the app runs exactly
// as before (no auth), so nothing breaks until you paste a real project config.

export const firebaseConfig = {
    apiKey: "AIzaSyBr9rT2lYfQO7E3PPQ3xu6Yp-DTlVwmUu8",
    authDomain: "gmatwiz.firebaseapp.com",
    projectId: "gmatwiz",
    storageBucket: "gmatwiz.firebasestorage.app",
    messagingSenderId: "959292194702",
    appId: "1:959292194702:web:c35598bcf04a02c96eaedf",
    measurementId: "G-QLQFXQHWNF",
};
