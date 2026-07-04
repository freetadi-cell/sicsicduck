// Firebase Cloud Messaging Service Worker
importScripts('https://www.gstatic.com/firebasejs/12.13.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/12.13.0/firebase-messaging-compat.js');

const firebaseConfig = {
    apiKey: "AIzaSyD_czqEXtqtnF2sEP8fmAJt6hyMTdhjXWI",
    authDomain: "sicsicduck.firebaseapp.com",
    databaseURL: "https://sicsicduck-default-rtdb.firebaseio.com",
    projectId: "sicsicduck",
    storageBucket: "sicsicduck.firebasestorage.app",
    messagingSenderId: "606277142508",
    appId: "1:606277142508:web:d342c4480fed45d85422c9"
};

firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// Handle background messages
messaging.onBackgroundMessage((payload) => {
    console.log('Received background message:', payload);
    
    const notificationTitle = payload.notification.title || '食息鴨';
    const notificationOptions = {
        body: payload.notification.body || '',
        icon: '/favicon.ico',
        badge: '/favicon.ico',
        tag: 'sicsicduck-rate-update',
        data: payload.data
    };

    self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
    console.log('Notification clicked:', event);
    event.notification.close();
    
    // Open or focus the website
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            for (const client of clientList) {
                if (client.url === 'https://sicsicduck.com/' && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow('https://sicsicduck.com/');
            }
        })
    );
});