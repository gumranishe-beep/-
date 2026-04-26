// ===== TELEGRAM WEB APP INIT =====
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// Тема
if (tg.colorScheme === 'dark') {
    document.body.classList.add('dark');
}

// ===== STATE =====
const state = {
    user: null,
    subscription: {
        trafficUsed: 0,
        trafficLimit: Infinity,
        devices: [],
        deviceLimit: 3,
        isActive: false,
        server: null
    },
    shiba: {
        mood: 'happy',
        lastFed: null,
        hunger: 100,
        animationState: 'idle'
    },
    referrals: [],
    rating: [],
    currentScreen: 'main'
};

// ===== INIT =====
document.addEventListener('DOMContentLoaded', async () => {
    // Анимация загрузки
    await simulateLoading();

    // Инициализация пользователя
    initUser();

    // Загрузка данных
    await loadUserData();

    // Показ главного экрана
    showScreen('main');

    // Обновление UI
    updateUI();

    // Запуск анимаций Шибы
    startShibaAnimations();
});

// ===== LOADING =====
function simulateLoading() {
    return new Promise(resolve => {
        const progress = document.querySelector('.loading-progress');
        let width = 0;
        const interval = setInterval(() => {
            width += Math.random() * 30;
            if (width >= 100) {
                width = 100;
                clearInterval(interval);
                setTimeout(() => {
                    document.getElementById('loading-screen').classList.add('hidden');
                    document.getElementById('main-screen').classList.remove('hidden');
                    resolve();
                }, 500);
            }
            progress.style.width = width + '%';
        }, 300);
    });
}

// ===== USER INIT =====
function initUser() {
    const user = tg.initDataUnsafe.user;
    if (user) {
        state.user = {
            id: user.id,
            username: user.username || user.first_name || 'Пользователь',
            photo_url: user.photo_url
        };

        document.getElementById('username').textContent = state.user.username;
        document.getElementById('user-id').textContent = `ID: ${state.user.id}`;

        if (state.user.photo_url) {
            document.getElementById('user-avatar').style.backgroundImage = `url(${state.user.photo_url})`;
            document.getElementById('user-avatar').style.backgroundSize = 'cover';
        } else {
            document.getElementById('user-avatar').textContent = '🐕';
        }
    }
}

// ===== API CALLS =====
const API_BASE = '/api'; // Заменить на реальный URL бэкенда

async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Init-Data': tg.initData
        }
    };
    if (body) options.body = JSON.stringify(body);

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        return null;
    }
}

async function loadUserData() {
    // В реальном приложении здесь будет запрос к бэкенду
    // const data = await apiCall('/user/profile');

    // Мок-данные для демо
    state.subscription.devices = [
        { id: 1, name: 'iPhone X', type: 'phone', status: 'active' }
    ];
    state.subscription.trafficUsed = 1.2;
    state.shiba.lastFed = new Date(Date.now() - 3600000).toISOString();
    state.shiba.hunger = 75;

    state.rating = [
        { place: 1, name: 'A_c***', total: 4386, active: 1738 },
        { place: 2, name: 'ara***', total: 1370, active: 586 },
        { place: 3, name: 'Kny***', total: 1229, active: 533 },
        { place: 4, name: 'sla***', total: 1225, active: 515 },
        { place: 5, name: 'Ale***', total: 196, active: 111 },
    ];
}

// ===== SCREEN MANAGEMENT =====
const screens = ['main', 'referral', 'quests', 'minigame', 'daily', 'news', 'support', 'faq'];
let screenHistory = [];

function showScreen(screenName) {
    // Скрыть все экраны
    screens.forEach(s => {
        const el = document.getElementById(s + '-screen');
        if (el) el.classList.add('hidden');
    });

    // Скрыть меню
    document.getElementById('profile-menu').classList.add('hidden');

    // Показать нужный экран
    const targetScreen = document.getElementById(screenName + '-screen');
    if (targetScreen) {
        targetScreen.classList.remove('hidden');
        screenHistory.push(state.currentScreen);
        state.currentScreen = screenName;
    }

    // Обновить кнопку назад
    updateBackButton();

    // Специальные действия для экранов
    if (screenName === 'referral') renderRating();
    if (screenName === 'main') updateShibaAnimation();
}

function goBack() {
    const prevScreen = screenHistory.pop() || 'main';
    showScreen(prevScreen);
}

function updateBackButton() {
    const backBtn = document.querySelector('.back-btn');
    if (backBtn) {
        if (state.currentScreen === 'main') {
            backBtn.classList.add('hidden');
        } else {
            backBtn.classList.remove('hidden');
        }
    }
}

function closeApp() {
    tg.close();
}

function toggleMenu() {
    const menu = document.getElementById('profile-menu');
    menu.classList.toggle('hidden');
}

// ===== SHIBA ANIMATIONS =====
function startShibaAnimations() {
    updateShibaAnimation();

    // Периодические случайные анимации
    setInterval(() => {
        if (state.shiba.animationState === 'idle') {
            const randomActions = ['blink', 'earWiggle', 'tailWag'];
            const action = randomActions[Math.floor(Math.random() * randomActions.length)];
            triggerShibaAction(action);
        }
    }, 5000);
}

function updateShibaAnimation() {
    const shiba = document.getElementById('shiba-character');
    const message = document.getElementById('shiba-message');
    const status = document.getElementById('shiba-status');

    // Сброс классов
    shiba.className = 'shiba-character';

    if (state.subscription.isActive) {
        // Подписка активна - Шиба танцует!
        shiba.classList.add('dancing');
        state.shiba.animationState = 'dancing';
        status.textContent = 'VPN подключен! Танцую! 💃';
        status.style.color = 'var(--success)';
        message.textContent = 'Гав-гав! VPN работает! Я так счастлива! 🎉';

        // Добавить звёзды
        createStars();
    } else if (state.shiba.hunger < 30) {
        // Шиба голодна
        state.shiba.animationState = 'sad';
        status.textContent = 'Голодная... 🥺';
        status.style.color = 'var(--error)';
        message.textContent = 'Я проголодалась... Накорми меня, пожалуйста? 🍖';
    } else if (state.shiba.hunger < 70) {
        // Шиба нормальная
        state.shiba.animationState = 'idle';
        status.textContent = 'Всё ок! 😊';
        status.style.color = 'var(--warning)';
        message.textContent = 'Привет! Подключи VPN и я станцую для тебя! 🐕';
    } else {
        // Шиба счастлива
        shiba.classList.add('happy');
        state.shiba.animationState = 'happy';
        status.textContent = 'Сыта и счастлива! 🥰';
        status.style.color = 'var(--success)';
        message.textContent = 'Спасибо за еду! Я готова защищать твой интернет! 🛡️';
    }
}

function triggerShibaAction(action) {
    const shiba = document.getElementById('shiba-character');

    switch(action) {
        case 'blink':
            // Моргание уже в CSS анимации
            break;
        case 'earWiggle':
            const ears = shiba.querySelectorAll('.ear');
            ears.forEach(ear => {
                ear.style.animation = 'none';
                setTimeout(() => {
                    ear.style.animation = '';
                }, 10);
            });
            break;
        case 'tailWag':
            const tail = shiba.querySelector('.tail');
            tail.style.animation = 'none';
            setTimeout(() => {
                tail.style.animation = 'tailWag 0.5s ease infinite';
            }, 10);
            break;
    }
}

function createHearts() {
    const container = document.getElementById('hearts-effect');
    container.innerHTML = '';

    for (let i = 0; i < 6; i++) {
        setTimeout(() => {
            const heart = document.createElement('div');
            heart.className = 'heart-particle';
            heart.textContent = ['❤️', '💖', '💕', '💗'][Math.floor(Math.random() * 4)];
            heart.style.left = (20 + Math.random() * 60) + '%';
            heart.style.top = (30 + Math.random() * 40) + '%';
            heart.style.animationDelay = (Math.random() * 0.5) + 's';
            container.appendChild(heart);

            setTimeout(() => heart.remove(), 2000);
        }, i * 200);
    }
}

function createStars() {
    const container = document.getElementById('stars-effect');
    container.innerHTML = '';

    for (let i = 0; i < 8; i++) {
        setTimeout(() => {
            const star = document.createElement('div');
            star.className = 'star-particle';
            star.textContent = ['⭐', '✨', '🌟', '💫'][Math.floor(Math.random() * 4)];
            star.style.left = (10 + Math.random() * 80) + '%';
            star.style.top = (20 + Math.random() * 50) + '%';
            star.style.animationDelay = (Math.random() * 0.3) + 's';
            container.appendChild(star);

            setTimeout(() => star.remove(), 2000);
        }, i * 150);
    }
}

// ===== FEED SHIBA =====
async function feedShiba() {
    const shiba = document.getElementById('shiba-character');
    const btn = document.getElementById('feed-btn');

    // Проверка cooldown (раз в 4 часа)
    const lastFed = state.shiba.lastFed ? new Date(state.shiba.lastFed) : null;
    const now = new Date();
    if (lastFed && (now - lastFed) < 4 * 3600000) {
        const hoursLeft = Math.ceil((4 * 3600000 - (now - lastFed)) / 3600000);
        showNotification(`Шиба уже сыта! Покорми через ${hoursLeft} ч. 🍖`);
        return;
    }

    // Анимация поедания
    shiba.classList.add('eating');
    state.shiba.animationState = 'eating';

    // Показать миску
    showNotification('Ням-ням! 🍖 Шиба ест...');

    // Эффекты
    createHearts();

    // Кнопка неактивна
    btn.disabled = true;
    btn.innerHTML = '<span>Шиба ест... 🍖</span>';

    setTimeout(async () => {
        // Обновить состояние
        state.shiba.lastFed = now.toISOString();
        state.shiba.hunger = 100;
        state.shiba.mood = 'happy';

        // Добавить бонус трафика
        state.subscription.trafficUsed = Math.max(0, state.subscription.trafficUsed - 0.1);

        // В реальном приложении - запрос к API
        // await apiCall('/shiba/feed', 'POST');

        // Вернуть кнопку
        btn.disabled = false;
        btn.innerHTML = '<span>Накормить Шибу 🍖</span>';

        // Обновить анимацию
        shiba.classList.remove('eating');
        updateShibaAnimation();

        showNotification('Шиба накормлена! +100 МБ бонуса! 🎉');
        updateUI();
    }, 2000);
}

// ===== VPN CONNECTION =====
function connectVPN() {
    document.getElementById('connect-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('connect-modal').classList.add('hidden');
}

async function selectServer(serverCode) {
    closeModal();

    const servers = {
        'ru': { name: 'Россия', flag: '🇷🇺' },
        'de': { name: 'Германия', flag: '🇩🇪' },
        'nl': { name: 'Нидерланды', flag: '🇳🇱' },
        'us': { name: 'США', flag: '🇺🇸' },
        'sg': { name: 'Сингапур', flag: '🇸🇬' }
    };

    const server = servers[serverCode];
    showNotification(`Подключаемся к ${server.flag} ${server.name}...`);

    // В реальном приложении - запрос конфигурации VPN
    // const config = await apiCall(`/vpn/connect/${serverCode}`, 'POST');

    setTimeout(() => {
        state.subscription.isActive = true;
        state.subscription.server = serverCode;

        // Обновить UI
        document.getElementById('connect-btn').classList.add('hidden');
        document.getElementById('feed-btn').classList.remove('hidden');

        // Шиба танцует!
        updateShibaAnimation();

        showNotification(`✅ Подключено к ${server.flag} ${server.name}! Шиба танцует! 🎉`);
        updateUI();
    }, 1500);
}

// ===== REFERRAL SYSTEM =====
function renderRating() {
    const list = document.getElementById('rating-list');
    if (!list || state.rating.length === 0) return;

    list.innerHTML = state.rating.map(user => `
        <div class="rating-item">
            <span class="rating-place">${user.place}</span>
            <span class="rating-name">${user.name}</span>
            <div class="rating-stats">
                <span class="rating-total">${user.total}</span>
                <span class="rating-active">${user.active}</span>
            </div>
        </div>
    `).join('');
}

function shareStory() {
    tg.showPopup({
        title: 'Поделиться',
        message: 'Отправь друзьям реферальную ссылку!',
        buttons: [
            { id: 'share', type: 'default', text: 'Поделиться' },
            { id: 'cancel', type: 'cancel' }
        ]
    }, (buttonId) => {
        if (buttonId === 'share') {
            const refLink = `https://t.me/ShibaVPNBot?start=ref_${state.user?.id || 'demo'}`;
            tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(refLink)}&text=${encodeURIComponent('Бесплатный VPN с Шибой-ину! 🐕🛡️')}`);
        }
    });
}

function shareLink() {
    const refLink = `https://t.me/ShibaVPNBot?start=ref_${state.user?.id || 'demo'}`;
    tg.showPopup({
        title: 'Реферальная ссылка',
        message: refLink,
        buttons: [
            { id: 'copy', type: 'default', text: 'Копировать' },
            { id: 'cancel', type: 'cancel' }
        ]
    });
}

function showQR() {
    showNotification('QR-код в разработке 📱');
}

function copyLink() {
    const refLink = `https://t.me/ShibaVPNBot?start=ref_${state.user?.id || 'demo'}`;
    navigator.clipboard.writeText(refLink).then(() => {
        showNotification('Ссылка скопирована! 📋');
    });
}

// ===== DEVICES =====
function renderDevices() {
    const list = document.getElementById('devices-list');
    const count = document.getElementById('devices-count');
    const total = document.getElementById('devices-total');
    const bar = document.getElementById('devices-bar');

    if (!list) return;

    const devices = state.subscription.devices;
    const limit = state.subscription.deviceLimit;

    count.textContent = `${devices.length} / ${limit}`;
    total.textContent = `${devices.length}/${limit}`;
    bar.style.width = `${(devices.length / limit) * 100}%`;

    if (devices.length === 0) {
        list.innerHTML = '<div class="add-device-hint">Нет подключённых устройств</div>';
        return;
    }

    list.innerHTML = devices.map(device => `
        <div class="device-item">
            <span class="device-icon">${getDeviceIcon(device.type)}</span>
            <div class="device-info">
                <span class="device-name">${device.name}</span>
                <span class="device-status">${device.status === 'active' ? '🟢 Активно' : '⚪ Неактивно'}</span>
            </div>
            <span class="device-delete" onclick="removeDevice(${device.id})">🗑️</span>
        </div>
    `).join('');
}

function getDeviceIcon(type) {
    const icons = {
        'phone': '📱',
        'tablet': '📲',
        'computer': '💻',
        'tv': '📺'
    };
    return icons[type] || '📱';
}

async function removeDevice(deviceId) {
    tg.showPopup({
        title: 'Удалить устройство?',
        message: 'Это устройство будет отключено от VPN.',
        buttons: [
            { id: 'delete', type: 'destructive', text: 'Удалить' },
            { id: 'cancel', type: 'cancel' }
        ]
    }, async (buttonId) => {
        if (buttonId === 'delete') {
            state.subscription.devices = state.subscription.devices.filter(d => d.id !== deviceId);

            // В реальном приложении
            // await apiCall(`/devices/${deviceId}`, 'DELETE');

            renderDevices();
            showNotification('Устройство удалено 🗑️');
        }
    });
}

// ===== UI UPDATE =====
function updateUI() {
    // Трафик
    const trafficUsed = state.subscription.trafficUsed;
    document.getElementById('traffic-used').textContent = `${trafficUsed.toFixed(1)} ГБ / ∞`;
    document.getElementById('download-stat').textContent = `${trafficUsed.toFixed(1)} ГБ`;

    // Устройства
    renderDevices();

    // Кнопки
    const feedBtn = document.getElementById('feed-btn');
    const connectBtn = document.getElementById('connect-btn');

    if (state.subscription.isActive) {
        feedBtn.classList.remove('hidden');
        connectBtn.classList.add('hidden');
    } else {
        feedBtn.classList.remove('hidden');
        connectBtn.classList.remove('hidden');
    }

    // Серверы
    document.getElementById('servers-stat').textContent = '5';
}

// ===== NOTIFICATIONS =====
function showNotification(text) {
    const notif = document.getElementById('notification');
    const textEl = document.getElementById('notification-text');

    textEl.textContent = text;
    notif.classList.remove('hidden');

    // Haptic feedback
    if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
    }

    setTimeout(() => {
        notif.classList.add('hidden');
    }, 3000);
}

// ===== FAQ =====
function toggleFaq(element) {
    element.classList.toggle('open');
}

// ===== SUPPORT =====
function openSupportChat() {
    tg.openTelegramLink('https://t.me/ShibaVPNSupport');
}

function openChannel() {
    tg.openTelegramLink('https://t.me/ShibaVPNNews');
}

// ===== EVENT LISTENERS =====
// Закрытие меню по клику вне
 document.addEventListener('click', (e) => {
    const menu = document.getElementById('profile-menu');
    const menuBtn = document.querySelector('.menu-btn');

    if (!menu.classList.contains('hidden') && 
        !menu.contains(e.target) && 
        !menuBtn.contains(e.target)) {
        menu.classList.add('hidden');
    }
});

// Обработка темы Telegram
tg.onEvent('themeChanged', () => {
    // Обновить цвета при смене темы
});

// ===== HAPTIC FEEDBACK =====
function haptic(type = 'light') {
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred(type);
    }
}

// Экспорт для отладки
window.state = state;
window.showScreen = showScreen;
window.feedShiba = feedShiba;
window.connectVPN = connectVPN;
window.selectServer = selectServer;
