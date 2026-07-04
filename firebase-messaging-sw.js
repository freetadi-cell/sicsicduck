importScripts('https://www.gstatic.com/firebasejs/12.13.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/12.13.0/firebase-messaging-compat.js');

firebase.initializeApp({
    apiKey: "AIzaSy…jXWI",
    authDomain: "sicsicduck.firebaseapp.com",
    databaseURL: "https://sicsicduck-default-rtdb.firebaseio.com",
    projectId: "sicsicduck",
    storageBucket: "sicsicduck.firebasestorage.app",
    messagingSenderId: "606277142508",
    appId: "1:606277142508:web:d342c4480fed45d85422c9"
});

const messaging = firebase.messaging();

// 不需要 onBackgroundMessage，因為 FCM 會自動顯示通知
// 移除此 handler 避免雙重通知

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(clients.openWindow('https://sicsicduck.com'));
});
