/**
 * app.js — Lógica principal de la aplicación cliente del robot de reparto.
 *
 * Gestiona:
 * - Conexión MQTT vía WebSockets al broker central
 * - Recepción del mapa y actualización del renderizador
 * - Creación y envío de pedidos al robot
 * - Visualización de la odometría en tiempo real (≥1 Hz)
 * - Estado del robot y cola de pedidos
 */

// =============================================================================
// CONFIGURACIÓN
// =============================================================================

const CONFIG = {
    // MQTT Broker
    BROKER_HOST: '192.168.1.134',
    BROKER_WS_PORT: 1883,
    BROKER_URL: 'ws://192.168.1.134:1883/mqtt',

    // Team
    TEAM_LETTER: 'F',

    // Topics
    TOPIC_MAP: 'map',
    get TOPIC_ODOMETRY() { return `Equipo ${this.TEAM_LETTER}/odometria`; },
    get TOPIC_ORDERS() { return `Equipo ${this.TEAM_LETTER}/pedidos`; },
    get TOPIC_STATUS() { return `Equipo ${this.TEAM_LETTER}/estado`; },

    // Reconnect
    RECONNECT_INTERVAL: 5000,

    // Simulation
    SIMULATION_MODE: false,  // Conectando al broker MQTT real
};

// =============================================================================
// STATE
// =============================================================================

const state = {
    mqttClient: null,
    connected: false,
    mapLoaded: false,
    mapString: null,
    orders: [],           // Array of { id, pickup, delivery, status }
    orderIdCounter: 0,
    robotState: {
        status: 'idle',
        row: 4,   // Start position (row 4 in 0-indexed 5-row grid)
        col: 0,
        heading: 'up',
        headingAngle: 0,
        distance: 0,
        speed: 0,
        angle: 0,
        turnRate: 0,
    },
    odometryTimestamps: [],  // For calculating refresh rate
};

// Status labels in Spanish
const STATUS_LABELS = {
    'idle': '⏳ Esperando',
    'navigating_pickup': '🚗 Hacia recogida',
    'navigating_delivery': '🚗 Hacia entrega',
    'picking_up': '📦 Recogiendo',
    'delivering': '📤 Entregando',
    'completed': '✅ Completado',
    'error': '❌ Error',
};

// Heading labels
const HEADING_LABELS = {
    'up': '↑ Arriba (0°)',
    'right': '→ Derecha (90°)',
    'down': '↓ Abajo (180°)',
    'left': '← Izquierda (270°)',
};

// =============================================================================
// MQTT CONNECTION
// =============================================================================

function connectMQTT() {
    updateConnectionStatus(false, 'Conectando...');

    if (CONFIG.SIMULATION_MODE) {
        console.log('🎮 Modo Simulación activo');
        updateConnectionStatus(false, 'Simulación');
        startSimulation();
        return;
    }

    try {
        const client = mqtt.connect(CONFIG.BROKER_URL, {
            clientId: `webapp_equipo_${CONFIG.TEAM_LETTER}_${Date.now()}`,
            clean: true,
            connectTimeout: 4000,
            reconnectPeriod: CONFIG.RECONNECT_INTERVAL,
        });

        client.on('connect', () => {
            console.log('✅ Conectado al broker MQTT');
            state.connected = true;
            state.mqttClient = client;
            updateConnectionStatus(true, 'Conectado');
            showToast('Conectado al servidor MQTT', 'success');

            // Subscribe to topics
            client.subscribe(CONFIG.TOPIC_MAP, { qos: 0 });
            client.subscribe(CONFIG.TOPIC_ODOMETRY, { qos: 0 });
            client.subscribe(CONFIG.TOPIC_STATUS, { qos: 0 });
        });

        client.on('message', (topic, message) => {
            const payload = message.toString();

            if (topic === CONFIG.TOPIC_MAP) {
                handleMapMessage(payload);
            } else if (topic === CONFIG.TOPIC_ODOMETRY) {
                handleOdometryMessage(payload);
            } else if (topic === CONFIG.TOPIC_STATUS) {
                handleStatusMessage(payload);
            }
        });

        client.on('error', (err) => {
            console.error('MQTT Error:', err);
            updateConnectionStatus(false, 'Error');
        });

        client.on('close', () => {
            state.connected = false;
            updateConnectionStatus(false, 'Desconectado');
        });

        client.on('reconnect', () => {
            updateConnectionStatus(false, 'Reconectando...');
        });

    } catch (err) {
        console.error('Error connecting to MQTT:', err);
        updateConnectionStatus(false, 'Error');
        showToast('Error al conectar con el broker MQTT', 'error');
    }
}

// =============================================================================
// MESSAGE HANDLERS
// =============================================================================

function handleMapMessage(payload) {
    console.log('🗺️ Mapa recibido:', payload.substring(0, 30) + '...');
    state.mapString = payload;
    state.mapLoaded = true;

    const result = MapRenderer.setMap(payload);
    updateMapStatus(true);
    populatePickupSelectors(MapRenderer.getPickupPoints());
    showToast('Mapa de la ciudad recibido', 'success');
}

function handleOdometryMessage(payload) {
    try {
        const data = JSON.parse(payload);
        state.robotState.row = data.row;
        state.robotState.col = data.col;
        state.robotState.heading = data.heading;
        state.robotState.headingAngle = data.heading_angle || 0;
        state.robotState.distance = data.distance || 0;
        state.robotState.speed = data.speed || 0;
        state.robotState.angle = data.angle || 0;
        state.robotState.turnRate = data.turn_rate || 0;

        // Update UI
        updateOdometryUI();
        updatePositionUI();

        // Update map
        MapRenderer.setRobotPosition(data.row, data.col, data.heading_angle);

        // Track refresh rate
        trackOdometryRate();
    } catch (e) {
        console.error('Error parsing odometry:', e);
    }
}

function handleStatusMessage(payload) {
    try {
        const data = JSON.parse(payload);
        state.robotState.status = data.status;
        updateRobotStatusUI(data.status);

        if (data.status === 'completed') {
            markCurrentOrderCompleted();
        }
    } catch (e) {
        console.error('Error parsing status:', e);
    }
}

// =============================================================================
// ORDER MANAGEMENT
// =============================================================================

function submitOrder(pickup, delivery) {
    const order = {
        id: ++state.orderIdCounter,
        pickup: pickup,
        delivery: delivery,
        status: state.orders.length === 0 ? 'active' : 'queued',
        timestamp: new Date().toLocaleTimeString(),
    };

    state.orders.push(order);

    // Send to MQTT
    const mqttPayload = JSON.stringify({
        pickup: pickup,
        delivery: delivery,
    });

    if (state.mqttClient && state.connected) {
        state.mqttClient.publish(CONFIG.TOPIC_ORDERS, mqttPayload);
    }

    updateOrderQueueUI();
    showToast(`Pedido #${order.id} añadido`, 'info');
    console.log('📦 Pedido enviado:', order);
}

function markCurrentOrderCompleted() {
    const activeOrder = state.orders.find(o => o.status === 'active');
    if (activeOrder) {
        activeOrder.status = 'completed';

        // Activate next queued order
        const nextOrder = state.orders.find(o => o.status === 'queued');
        if (nextOrder) {
            nextOrder.status = 'active';
        }

        updateOrderQueueUI();
        showToast(`Pedido #${activeOrder.id} completado! ✅`, 'success');
    }
}

// =============================================================================
// UI UPDATES
// =============================================================================

function updateConnectionStatus(connected, text) {
    const dot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');

    if (connected) {
        dot.classList.add('connected');
    } else {
        dot.classList.remove('connected');
    }
    statusText.textContent = text;
}

function updateMapStatus(loaded) {
    const chip = document.getElementById('map-status');
    if (loaded) {
        chip.textContent = 'Mapa cargado';
        chip.classList.remove('loading');
        chip.classList.add('loaded');
    } else {
        chip.textContent = 'Sin mapa';
        chip.classList.add('loading');
        chip.classList.remove('loaded');
    }
}

function updateOdometryUI() {
    const s = state.robotState;
    document.getElementById('odo-distance').textContent = `${Math.round(s.distance)} mm`;
    document.getElementById('odo-speed').textContent = `${Math.round(s.speed)} mm/s`;
    document.getElementById('odo-angle').textContent = `${Math.round(s.angle)}°`;
    document.getElementById('odo-turn-rate').textContent = `${Math.round(s.turnRate)}°/s`;
}

function updatePositionUI() {
    const s = state.robotState;
    document.getElementById('robot-position').textContent = `(${s.row}, ${s.col})`;
    document.getElementById('robot-heading').textContent =
        HEADING_LABELS[s.heading] || `${s.headingAngle}°`;
    document.getElementById('robot-speed').textContent = `${Math.round(s.speed)} mm/s`;
}

function updateRobotStatusUI(status) {
    const el = document.getElementById('robot-state');
    el.textContent = STATUS_LABELS[status] || status;

    // Remove all status classes
    el.classList.remove('idle', 'navigating', 'picking', 'delivering', 'error');

    if (status === 'idle') el.classList.add('idle');
    else if (status.startsWith('navigating')) el.classList.add('navigating');
    else if (status === 'picking_up') el.classList.add('picking');
    else if (status === 'delivering') el.classList.add('delivering');
    else if (status === 'error') el.classList.add('error');
}

function updateOrderQueueUI() {
    const list = document.getElementById('order-list');
    const count = document.getElementById('order-count');
    const emptyQueue = document.getElementById('empty-queue');

    count.textContent = state.orders.filter(o => o.status !== 'completed').length;

    if (state.orders.length === 0) {
        emptyQueue.style.display = 'block';
        return;
    }

    emptyQueue.style.display = 'none';

    // Remove old items
    list.querySelectorAll('.order-item').forEach(el => el.remove());

    // Add order items (most recent first, but active/queued before completed)
    const sortedOrders = [...state.orders].sort((a, b) => {
        const priority = { active: 0, queued: 1, completed: 2 };
        return (priority[a.status] || 3) - (priority[b.status] || 3);
    });

    for (const order of sortedOrders) {
        const item = document.createElement('div');
        item.className = `order-item ${order.status}`;
        item.innerHTML = `
            <div class="order-details">
                <span class="order-label">Pedido #${order.id} — ${order.timestamp}</span>
                <span class="order-points">
                    📍 (${order.pickup[0]}, ${order.pickup[1]}) → 🏠 (${order.delivery[0]}, ${order.delivery[1]})
                </span>
            </div>
            <span class="order-status-badge ${order.status}">
                ${order.status === 'active' ? 'Activo' :
                  order.status === 'queued' ? 'En cola' : 'Hecho'}
            </span>
        `;
        list.appendChild(item);
    }
}

function populatePickupSelectors(pickupPoints) {
    const pickupSel = document.getElementById('pickup-select');
    const deliverySel = document.getElementById('delivery-select');

    // Clear existing options (keep the placeholder)
    pickupSel.innerHTML = '<option value="">Seleccionar punto...</option>';
    deliverySel.innerHTML = '<option value="">Seleccionar punto...</option>';

    for (const [row, col] of pickupPoints) {
        const label = `Bloque (${row}, ${col})`;
        const value = `${row},${col}`;

        pickupSel.innerHTML += `<option value="${value}">${label}</option>`;
        deliverySel.innerHTML += `<option value="${value}">${label}</option>`;
    }
}

function trackOdometryRate() {
    const now = Date.now();
    state.odometryTimestamps.push(now);

    // Keep only last 10 timestamps
    if (state.odometryTimestamps.length > 10) {
        state.odometryTimestamps.shift();
    }

    // Calculate rate
    if (state.odometryTimestamps.length >= 2) {
        const ts = state.odometryTimestamps;
        const elapsed = ts[ts.length - 1] - ts[0];
        const rate = ((ts.length - 1) / elapsed) * 1000;
        document.getElementById('odometry-rate').textContent = `${rate.toFixed(1)} Hz`;
    }
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// =============================================================================
// SIMULATION MODE
// =============================================================================

function startSimulation() {
    console.log('🎮 Starting simulation...');
    showToast('Modo simulación — conectar al broker para datos reales', 'info');

    // Load default map after a brief delay
    setTimeout(() => {
        // Default map from the project description
        const defaultMap = "02020001050307" +
                          "00000002020800" +
                          "01010010000200" +
                          "00000200020401" +
                          "07010901060100";
        handleMapMessage(defaultMap);

        // Set robot at start position
        MapRenderer.setRobotPosition(4, 0, 0);
        state.robotState.row = 4;
        state.robotState.col = 0;
        state.robotState.heading = 'up';
        updatePositionUI();
        updateRobotStatusUI('idle');
    }, 500);

    // Simulate odometry updates at ~2Hz
    setInterval(() => {
        const s = state.robotState;
        s.distance += Math.random() * 5;
        s.speed = 100 + Math.random() * 50;
        s.angle += Math.random() * 2 - 1;
        s.turnRate = Math.random() * 10 - 5;

        updateOdometryUI();
        trackOdometryRate();
    }, 500);
}

// =============================================================================
// EVENT HANDLERS
// =============================================================================

function setupEventListeners() {
    // Order form submission
    document.getElementById('order-form').addEventListener('submit', (e) => {
        e.preventDefault();

        const pickupVal = document.getElementById('pickup-select').value;
        const deliveryVal = document.getElementById('delivery-select').value;

        if (!pickupVal || !deliveryVal) {
            showToast('Selecciona punto de recogida y entrega', 'error');
            return;
        }

        if (pickupVal === deliveryVal) {
            showToast('Los puntos de recogida y entrega deben ser distintos', 'error');
            return;
        }

        // Check max 2 active orders (1 active + 1 queued)
        const pendingOrders = state.orders.filter(o => o.status !== 'completed');
        if (pendingOrders.length >= 2) {
            showToast('Máximo 2 pedidos simultáneos (1 activo + 1 en cola)', 'error');
            return;
        }

        const pickup = pickupVal.split(',').map(Number);
        const delivery = deliveryVal.split(',').map(Number);

        submitOrder(pickup, delivery);

        // Reset form
        document.getElementById('pickup-select').value = '';
        document.getElementById('delivery-select').value = '';
    });

    // Window resize
    window.addEventListener('resize', () => {
        MapRenderer.resize();
    });
}

// =============================================================================
// INITIALIZATION
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🤖 Robot de Reparto — Equipo F');
    console.log('================================');

    // Initialize map renderer
    MapRenderer.init('city-map-canvas');
    MapRenderer.resize();

    // Set up event listeners
    setupEventListeners();

    // Connect to MQTT (or start simulation)
    connectMQTT();

    // Set initial robot position on map
    MapRenderer.setRobotPosition(4, 0, 0);
    updateRobotStatusUI('idle');
});
