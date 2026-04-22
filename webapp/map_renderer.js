/**
 * map_renderer.js — Renderizador del mapa de la ciudad en Canvas.
 *
 * Dibuja el grid 7×5 con bloques de edificios, calles, puntos de
 * recogida/entrega, y la posición del robot en tiempo real.
 */

const MapRenderer = (() => {
    // =========================================================================
    // CONSTANTES
    // =========================================================================

    const MAP_ROWS = 5;
    const MAP_COLS = 7;

    // Direcciones de cada tipo de bloque
    const BLOCK_DIRECTIONS = {
        0:  [],                                         // Edificio
        1:  ['left', 'right'],                          // Izquierda-derecha
        2:  ['up', 'down'],                             // Arriba-abajo
        3:  ['up', 'right'],                            // Arriba-derecha
        4:  ['right', 'down'],                          // Derecha-abajo
        5:  ['down', 'left'],                           // Abajo-izquierda
        6:  ['left', 'up'],                             // Izquierda-arriba
        7:  ['left', 'up', 'right'],                    // Izquierda-arriba-derecha
        8:  ['up', 'right', 'down'],                    // Arriba-derecha-abajo
        9:  ['right', 'down', 'left'],                  // Derecha-abajo-izquierda
        10: ['down', 'left', 'up'],                     // Abajo-izquierda-arriba
        11: ['up', 'right', 'down', 'left'],            // Todas las direcciones
    };

    const OPPOSITE = { up: 'down', down: 'up', left: 'right', right: 'left' };
    const DIRECTION_DELTA = {
        up:    [-1,  0],
        down:  [ 1,  0],
        left:  [ 0, -1],
        right: [ 0,  1],
    };

    // Colors
    const COLORS = {
        background:     '#0c1220',
        gridLine:       'rgba(255, 255, 255, 0.04)',
        building:       '#dc2626',
        buildingStroke:  '#991b1b',
        buildingPattern: '#b91c1c',
        streetBg:       '#f1f5f9',
        streetLine:     '#1e293b',
        streetBlue:     '#3b82f6',
        streetGreen:    '#22c55e',
        centerSquare:   '#0f172a',
        pickup:         '#22d3ee',
        pickupGlow:     'rgba(34, 211, 238, 0.3)',
        robot:          '#fbbf24',
        robotGlow:      'rgba(251, 191, 36, 0.4)',
        robotDirection: '#f59e0b',
        pathLine:       'rgba(6, 182, 212, 0.3)',
        coordText:      'rgba(255, 255, 255, 0.3)',
    };

    // =========================================================================
    // STATE
    // =========================================================================

    let canvas = null;
    let ctx = null;
    let grid = null;
    let pickupPoints = [];
    let cellW = 0;
    let cellH = 0;
    let padding = 30;

    // Robot state
    let robotPos = null;      // { row, col }
    let robotAngle = 0;       // degrees (0 = up)
    let robotPath = [];       // planned path as [{row, col}, ...]

    // Animation
    let animFrame = null;
    let robotPulse = 0;

    // =========================================================================
    // INITIALIZATION
    // =========================================================================

    function init(canvasId) {
        canvas = document.getElementById(canvasId);
        if (!canvas) return;
        ctx = canvas.getContext('2d');

        // Make canvas high DPI
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();

        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        canvas.style.width = rect.width + 'px';
        canvas.style.height = rect.height + 'px';

        calculateCellSize();
        startAnimation();
    }

    function calculateCellSize() {
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        const availW = rect.width - padding * 2;
        const availH = rect.height - padding * 2;
        cellW = availW / MAP_COLS;
        cellH = availH / MAP_ROWS;
        // Keep square cells
        const cellSize = Math.min(cellW, cellH);
        cellW = cellSize;
        cellH = cellSize;
        // Recalculate padding to center
        padding = Math.max(
            (rect.width - cellW * MAP_COLS) / 2,
            (rect.height - cellH * MAP_ROWS) / 2
        );
    }

    // =========================================================================
    // MAP PARSING
    // =========================================================================

    function setMap(mapString) {
        grid = [];
        for (let row = 0; row < MAP_ROWS; row++) {
            grid[row] = [];
            for (let col = 0; col < MAP_COLS; col++) {
                const idx = (row * MAP_COLS + col) * 2;
                if (idx + 2 <= mapString.length) {
                    grid[row][col] = parseInt(mapString.substring(idx, idx + 2), 10);
                } else {
                    grid[row][col] = 0;
                }
            }
        }
        findPickupPoints();
        render();
        return { grid, pickupPoints };
    }

    function setGridData(gridData, pickupPts) {
        grid = gridData;
        pickupPoints = pickupPts || [];
        render();
    }

    function findPickupPoints() {
        pickupPoints = [];
        if (!grid) return;

        for (let row = 0; row < MAP_ROWS; row++) {
            for (let col = 0; col < MAP_COLS; col++) {
                const blockId = grid[row][col];
                if (blockId === 0) continue;

                const dirs = BLOCK_DIRECTIONS[blockId] || [];
                let connections = 0;
                for (const dir of dirs) {
                    const [dr, dc] = DIRECTION_DELTA[dir];
                    const nr = row + dr;
                    const nc = col + dc;
                    if (nr >= 0 && nr < MAP_ROWS && nc >= 0 && nc < MAP_COLS) {
                        const neighborId = grid[nr][nc];
                        const neighborDirs = BLOCK_DIRECTIONS[neighborId] || [];
                        if (neighborDirs.includes(OPPOSITE[dir])) {
                            connections++;
                        }
                    }
                }
                if (connections === 1) {
                    pickupPoints.push([row, col]);
                }
            }
        }
    }

    // =========================================================================
    // ROBOT STATE
    // =========================================================================

    function setRobotPosition(row, col, angle) {
        robotPos = { row, col };
        robotAngle = angle || 0;
    }

    function setRobotPath(path) {
        robotPath = path || [];
    }

    // =========================================================================
    // RENDERING
    // =========================================================================

    function startAnimation() {
        function animate() {
            robotPulse = (robotPulse + 0.03) % (Math.PI * 2);
            render();
            animFrame = requestAnimationFrame(animate);
        }
        animate();
    }

    function render() {
        if (!ctx || !canvas) return;

        const rect = canvas.getBoundingClientRect();
        ctx.clearRect(0, 0, rect.width, rect.height);

        // Background
        ctx.fillStyle = COLORS.background;
        ctx.fillRect(0, 0, rect.width, rect.height);

        if (!grid) {
            drawEmptyState(rect);
            return;
        }

        // Draw grid
        drawGrid();
        // Draw path
        drawPath();
        // Draw pickup points
        drawPickupPoints();
        // Draw robot
        drawRobot();
        // Draw coordinates
        drawCoordinates();
    }

    function drawEmptyState(rect) {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
        ctx.font = '600 16px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Esperando mapa del servidor MQTT...', rect.width / 2, rect.height / 2 - 15);
        ctx.font = '400 12px Inter, sans-serif';
        ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.fillText('El mapa se retransmite cada 60 segundos', rect.width / 2, rect.height / 2 + 15);
    }

    function drawGrid() {
        for (let row = 0; row < MAP_ROWS; row++) {
            for (let col = 0; col < MAP_COLS; col++) {
                const x = padding + col * cellW;
                const y = padding + row * cellH;
                const blockId = grid[row][col];

                if (blockId === 0) {
                    drawBuilding(x, y);
                } else {
                    drawStreetBlock(x, y, blockId);
                }
            }
        }
    }

    function drawBuilding(x, y) {
        // Building background
        ctx.fillStyle = COLORS.building;
        ctx.fillRect(x + 1, y + 1, cellW - 2, cellH - 2);

        // Building pattern (cross-hatch)
        ctx.strokeStyle = COLORS.buildingPattern;
        ctx.lineWidth = 0.5;
        const step = 8;
        for (let i = 0; i < cellW + cellH; i += step) {
            ctx.beginPath();
            ctx.moveTo(x + Math.max(0, i - cellH), y + Math.min(cellH, i));
            ctx.lineTo(x + Math.min(cellW, i), y + Math.max(0, i - cellW));
            ctx.stroke();
        }

        // Building icon (circle)
        const cx = x + cellW / 2;
        const cy = y + cellH / 2;
        ctx.beginPath();
        ctx.arc(cx, cy, Math.min(cellW, cellH) * 0.25, 0, Math.PI * 2);
        ctx.fillStyle = COLORS.buildingStroke;
        ctx.fill();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    function drawStreetBlock(x, y, blockId) {
        const dirs = BLOCK_DIRECTIONS[blockId] || [];
        const cx = x + cellW / 2;
        const cy = y + cellH / 2;
        const streetWidth = cellW * 0.35;

        // White background
        ctx.fillStyle = COLORS.streetBg;
        ctx.fillRect(x + 1, y + 1, cellW - 2, cellH - 2);

        // Draw street lines for each direction
        ctx.fillStyle = '#e2e8f0';

        for (const dir of dirs) {
            switch (dir) {
                case 'up':
                    ctx.fillRect(cx - streetWidth / 2, y, streetWidth, cellH / 2);
                    break;
                case 'down':
                    ctx.fillRect(cx - streetWidth / 2, cy, streetWidth, cellH / 2);
                    break;
                case 'left':
                    ctx.fillRect(x, cy - streetWidth / 2, cellW / 2, streetWidth);
                    break;
                case 'right':
                    ctx.fillRect(cx, cy - streetWidth / 2, cellW / 2, streetWidth);
                    break;
            }
        }

        // Draw border lines on streets
        ctx.strokeStyle = COLORS.streetLine;
        ctx.lineWidth = 1.5;

        for (const dir of dirs) {
            ctx.beginPath();
            switch (dir) {
                case 'up':
                    ctx.moveTo(cx - streetWidth / 2, y + 1);
                    ctx.lineTo(cx - streetWidth / 2, cy);
                    ctx.moveTo(cx + streetWidth / 2, y + 1);
                    ctx.lineTo(cx + streetWidth / 2, cy);
                    break;
                case 'down':
                    ctx.moveTo(cx - streetWidth / 2, cy);
                    ctx.lineTo(cx - streetWidth / 2, y + cellH - 1);
                    ctx.moveTo(cx + streetWidth / 2, cy);
                    ctx.lineTo(cx + streetWidth / 2, y + cellH - 1);
                    break;
                case 'left':
                    ctx.moveTo(x + 1, cy - streetWidth / 2);
                    ctx.lineTo(cx, cy - streetWidth / 2);
                    ctx.moveTo(x + 1, cy + streetWidth / 2);
                    ctx.lineTo(cx, cy + streetWidth / 2);
                    break;
                case 'right':
                    ctx.moveTo(cx, cy - streetWidth / 2);
                    ctx.lineTo(x + cellW - 1, cy - streetWidth / 2);
                    ctx.moveTo(cx, cy + streetWidth / 2);
                    ctx.lineTo(x + cellW - 1, cy + streetWidth / 2);
                    break;
            }
            ctx.stroke();
        }

        // Center square (reference point)
        const sqSize = Math.min(cellW, cellH) * 0.15;
        ctx.fillStyle = COLORS.centerSquare;
        ctx.fillRect(cx - sqSize / 2, cy - sqSize / 2, sqSize, sqSize);
    }

    function drawPickupPoints() {
        for (const [row, col] of pickupPoints) {
            const x = padding + col * cellW + cellW / 2;
            const y = padding + row * cellH + cellH / 2;
            const radius = Math.min(cellW, cellH) * 0.18;

            // Glow effect
            const pulseScale = 1 + Math.sin(robotPulse * 2) * 0.15;
            ctx.beginPath();
            ctx.arc(x, y, radius * pulseScale * 1.8, 0, Math.PI * 2);
            ctx.fillStyle = COLORS.pickupGlow;
            ctx.fill();

            // Main circle
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, Math.PI * 2);
            ctx.fillStyle = COLORS.pickup;
            ctx.fill();
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // "P" label
            ctx.fillStyle = '#0f172a';
            ctx.font = `700 ${radius * 1.1}px Inter, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('P', x, y + 1);
        }
    }

    function drawPath() {
        if (!robotPath || robotPath.length < 2) return;

        ctx.beginPath();
        ctx.strokeStyle = COLORS.pathLine;
        ctx.lineWidth = 3;
        ctx.setLineDash([6, 4]);

        for (let i = 0; i < robotPath.length; i++) {
            const x = padding + robotPath[i].col * cellW + cellW / 2;
            const y = padding + robotPath[i].row * cellH + cellH / 2;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }

        ctx.stroke();
        ctx.setLineDash([]);
    }

    function drawRobot() {
        if (!robotPos) return;

        const x = padding + robotPos.col * cellW + cellW / 2;
        const y = padding + robotPos.row * cellH + cellH / 2;
        const radius = Math.min(cellW, cellH) * 0.22;

        // Glow
        const pulseR = 1 + Math.sin(robotPulse) * 0.2;
        ctx.beginPath();
        ctx.arc(x, y, radius * pulseR * 2, 0, Math.PI * 2);
        ctx.fillStyle = COLORS.robotGlow;
        ctx.fill();

        // Robot body
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = COLORS.robot;
        ctx.fill();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Direction arrow
        const angleRad = (robotAngle - 90) * Math.PI / 180;
        const arrowLen = radius * 0.7;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(
            x + Math.cos(angleRad) * arrowLen,
            y + Math.sin(angleRad) * arrowLen
        );
        ctx.strokeStyle = COLORS.robotDirection;
        ctx.lineWidth = 3;
        ctx.lineCap = 'round';
        ctx.stroke();
        ctx.lineCap = 'butt';

        // Robot label
        ctx.fillStyle = '#0f172a';
        ctx.font = `800 ${radius * 0.9}px Inter, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('R', x, y + 1);
    }

    function drawCoordinates() {
        ctx.fillStyle = COLORS.coordText;
        ctx.font = '500 10px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Column labels
        for (let col = 0; col < MAP_COLS; col++) {
            const x = padding + col * cellW + cellW / 2;
            ctx.fillText(col.toString(), x, padding - 12);
        }

        // Row labels
        ctx.textAlign = 'right';
        for (let row = 0; row < MAP_ROWS; row++) {
            const y = padding + row * cellH + cellH / 2;
            ctx.fillText(row.toString(), padding - 10, y);
        }
    }

    // =========================================================================
    // RESIZE
    // =========================================================================

    function resize() {
        if (!canvas) return;
        const dpr = window.devicePixelRatio || 1;
        const parent = canvas.parentElement;
        const rect = parent.getBoundingClientRect();
        const width = rect.width - 40; // minus padding
        const height = Math.max(350, width * (MAP_ROWS / MAP_COLS) + 60);

        canvas.style.width = width + 'px';
        canvas.style.height = height + 'px';
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.scale(dpr, dpr);

        calculateCellSize();
        render();
    }

    // =========================================================================
    // PUBLIC API
    // =========================================================================

    return {
        init,
        setMap,
        setGridData,
        setRobotPosition,
        setRobotPath,
        render,
        resize,
        getPickupPoints: () => pickupPoints,
        getGrid: () => grid,
        MAP_ROWS,
        MAP_COLS,
    };
})();
