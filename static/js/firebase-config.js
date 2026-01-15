// static/js/firebase-config.js
// Firebase client-side configuration

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyDgdP28vV2L7a-qwqYZab1B4Fh8v43ywXA",
    authDomain: "mzansi-insights-28b51.firebaseapp.com",
    projectId: "mzansi-insights-28b51",
    storageBucket: "mzansi-insights-28b51.firebasestorage.app",
    messagingSenderId: "872256453178",
    appId: "1:872256453178:web:e22028d9d7d5198d705303",
    measurementId: "G-WXTXLDWH59"
};

// Initialize Firebase (if not already initialized)
if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
    
    // Initialize services
    const db = firebase.firestore();
    const analytics = firebase.analytics();
    
    // Enable offline persistence
    db.enablePersistence()
        .catch((err) => {
            console.log('Firebase persistence error:', err);
        });
    
    console.log('✅ Firebase client initialized');
}