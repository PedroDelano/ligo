let SIZE = 19;                 // will be updated from server
const board = [];              // 0 empty, 1 black, 2 white
for (let i = 0; i < SIZE; i++) board.push(Array(SIZE).fill(0));
let turn = 1;                  // 1 black, 2 white
let READY = false;
let GAME_ENDED = false;        // Track if game has ended
let WINNER = null;             // Track winner
let TERRITORY = null;          // Territory data
let SCORE = null;              // Score data
let MOVE_IN_PROGRESS = false;  // ADD THIS

let CELL = 30;           // px between lines (will be calculated)
let PADDING = 20;        // outer margin (will be calculated)

const meta = document.getElementById("meta");
const BOARD_ID = Number(meta.dataset.boardId);
const USER_COLOR = meta.dataset.userColor;
const canvas = document.getElementById("board");
const ctx = canvas.getContext("2d");
const dpr = Math.max(1, window.devicePixelRatio || 1);

let hover = { i: null, j: null, valid: false };
const CSRF_TOKEN = (() => {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
})();

// Calculate optimal cell size based on available container space
function calculateCellSize() {
    const container = document.querySelector('.board-container');
    if (!container) return 30;

    // Get container dimensions accounting for padding
    const containerWidth = container.clientWidth - 40;
    const containerHeight = container.clientHeight - 40;

    // Use the smaller dimension to ensure board fits
    const availableSpace = Math.min(containerWidth, containerHeight);

    // Calculate cell size - reserve space for stone radius on edges
    const stoneMargin = 30; // Extra margin for stones at edges
    const cellSize = Math.floor((availableSpace - stoneMargin) / (SIZE - 1));

    // Ensure minimum readable size
    CELL = Math.max(cellSize, 15);

    // Calculate padding to accommodate full stone radius plus margin
    const stoneRadius = Math.floor(CELL * 0.44);
    PADDING = stoneRadius + 8; // Add 8px extra margin

    return CELL;
}

// Helper functions to get dynamic dimensions
function getW() {
    return PADDING * 2 + CELL * (SIZE - 1);
}

function getH() {
    return getW();
}

function updateCanvasSize() {
    calculateCellSize();
    const W = getW();
    const H = getH();
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.scale(dpr, dpr);
}

async function loadBoard() {
    const res = await fetch(`/game/board/${BOARD_ID}/`, {
        method: "GET",
        credentials: "same-origin",
    });
    if (!res.ok) throw new Error("Failed to load board");
    const data = await res.json();
    const payload = data?.data ?? data;

    SIZE = payload.size;
    board.length = 0;
    for (let i = 0; i < SIZE; i++) board.push(Array(SIZE).fill(0));

    // Update canvas size based on new SIZE
    updateCanvasSize();

    const moves = Array.isArray(payload.moves) ? payload.moves : [];
    if (!payload.first_move && moves.length) {
        for (const mv of moves) {
            if (mv.x == -1 && mv.y == -1) continue; // pass move
            const color = mv.color === "B" ? 1 : 2;
            board[mv.x][mv.y] = color;
        }
    }
    turn = payload.next_color === "B" ? 1 : 2;

    // Update game ended state
    GAME_ENDED = payload.game_ended || false;
    WINNER = payload.winner || null;
    TERRITORY = payload.territory || null;
    SCORE = payload.score || null;

    updateTurnLabel();
    updateGameEndedUI();
    READY = true;
    render();
    clearMsg();
}

function updateGameEndedUI() {
    const passButton = document.getElementById("pass");
    const boardContainer = document.querySelector('.board-container');
    const scorePanel = document.getElementById("score-panel");

    if (GAME_ENDED) {
        // Disable pass button
        passButton.disabled = true;
        passButton.textContent = "Game Ended";

        // Add visual indicator to board
        boardContainer.classList.add('game-ended');

        // Show winner message
        const winnerText = WINNER === 'black' ? 'Black' : 'White';
        showMsg(`Game Over - ${winnerText} wins!`, 'success');

        // Update turn indicator to show winner
        const turnText = document.getElementById("turn-text");
        turnText.textContent = `Winner: ${winnerText}`;
        turnText.style.color = '#10b981';
        turnText.style.fontWeight = '700';

        // Display score panel
        if (SCORE && scorePanel) {
            scorePanel.style.display = 'block';
            updateScoreDisplay();
        }
    } else {
        // Reset UI for ongoing game
        passButton.disabled = false;
        passButton.textContent = "Pass Turn";
        boardContainer.classList.remove('game-ended');
        if (scorePanel) {
            scorePanel.style.display = 'none';
        }
    }
}

function updateScoreDisplay() {
    if (!SCORE) return;

    document.getElementById('black-stones').textContent = SCORE.black_stones;
    document.getElementById('black-territory').textContent = SCORE.black_territory;
    document.getElementById('black-total').textContent = SCORE.black_total.toFixed(1);

    document.getElementById('white-stones').textContent = SCORE.white_stones;
    document.getElementById('white-territory').textContent = SCORE.white_territory;
    document.getElementById('white-komi').textContent = SCORE.komi;
    document.getElementById('white-total').textContent = SCORE.white_total.toFixed(1);

    document.getElementById('final-winner').textContent = SCORE.winner === 'black' ? 'Black' : 'White';
    document.getElementById('final-margin').textContent = SCORE.margin.toFixed(1);
}

async function sendMove(i, j) {
    if (GAME_ENDED) {
        showMsg("Game has ended - no more moves allowed");
        return;
    }

    // ADD THIS CHECK
    if (MOVE_IN_PROGRESS) {
        console.log("Move already in progress, ignoring click");
        return;
    }

    // ADD THIS FLAG
    MOVE_IN_PROGRESS = true;

    try {
        const res = await fetch(`/game/place/${BOARD_ID}/${i}/${j}/`, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": CSRF_TOKEN }
        });

        const payload = await res.json();
        if (!res.ok || payload.ok === false) {
            showMsg(payload.message || "Move rejected");
            return;
        }
        clearMsg();
    } finally {
        // ADD THIS - release lock after a short delay to prevent rapid clicks
        setTimeout(() => {
            MOVE_IN_PROGRESS = false;
        }, 300);
    }
}

function showMsg(s, type = 'info') {
    const m = document.getElementById("msg");
    m.textContent = s;
    m.className = `message ${type}`;
}

function clearMsg() {
    const m = document.getElementById("msg");
    m.textContent = "";
    m.className = "message";
}

const coordToPx = (i, j) => ({
    x: PADDING + i * CELL,
    y: PADDING + j * CELL
});

const pxToCoord = (x, y) => {
    const i = Math.round((x - PADDING) / CELL);
    const j = Math.round((y - PADDING) / CELL);
    if (i < 0 || i >= SIZE || j < 0 || j >= SIZE) return { i: null, j: null, valid: false };
    return { i, j, valid: true };
};

function drawBoard() {
    const W = getW();
    const H = getH();

    // Clear and draw background
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#d6b26b";
    ctx.fillRect(0, 0, W, H);

    // Draw grid
    ctx.strokeStyle = "#6f4d22";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let n = 0; n < SIZE; n++) {
        // vertical
        const x = PADDING + n * CELL;
        ctx.moveTo(x, PADDING);
        ctx.lineTo(x, H - PADDING);
        // horizontal
        const y = PADDING + n * CELL;
        ctx.moveTo(PADDING, y);
        ctx.lineTo(W - PADDING, y);
    }
    ctx.stroke();

    // Draw star points
    drawStarPoints();

    // Draw territory indicators if game ended
    if (GAME_ENDED && TERRITORY) {
        drawTerritories();
    }
}

function drawTerritories() {
    if (!TERRITORY) return;

    const r = Math.floor(CELL * 0.25);

    // Draw black territory
    ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
    for (const [i, j] of TERRITORY.black) {
        const { x, y } = coordToPx(i, j);
        ctx.fillRect(x - r, y - r, r * 2, r * 2);
    }

    // Draw white territory
    ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
    ctx.strokeStyle = "rgba(0, 0, 0, 0.3)";
    ctx.lineWidth = 1;
    for (const [i, j] of TERRITORY.white) {
        const { x, y } = coordToPx(i, j);
        ctx.fillRect(x - r, y - r, r * 2, r * 2);
        ctx.strokeRect(x - r, y - r, r * 2, r * 2);
    }

    // Draw neutral territory (dame)
    ctx.fillStyle = "rgba(128, 128, 128, 0.2)";
    for (const [i, j] of TERRITORY.neutral) {
        const { x, y } = coordToPx(i, j);
        ctx.fillRect(x - r, y - r, r * 2, r * 2);
    }
}

function drawStarPoints() {
    let stars = [];
    if (SIZE === 19) {
        stars = [3, 9, 15];
    } else if (SIZE === 13) {
        stars = [3, 6, 9];
    } else if (SIZE === 9) {
        stars = [2, 4, 6];
    }

    if (stars.length > 0) {
        ctx.fillStyle = "#443014";
        for (const i of stars) {
            for (const j of stars) {
                const { x, y } = coordToPx(i, j);
                ctx.beginPath();
                ctx.arc(x, y, 2.5, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }
}

function drawStone(i, j, color, alpha = 1) {
    const { x, y } = coordToPx(i, j);
    const r = Math.floor(CELL * 0.44);

    // skip if pass move
    if (x == -1 || y == -1) return;

    ctx.save();
    ctx.globalAlpha = alpha;

    // Draw stone
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.closePath();

    if (color === 1) {
        // Black stone with gradient
        const grad = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, r * 0.1, x, y, r);
        grad.addColorStop(0, "#666");
        grad.addColorStop(1, "#111");
        ctx.fillStyle = grad;
        ctx.fill();
    } else {
        // White stone
        ctx.fillStyle = "#f7f7f7";
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,.2)";
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    // Draw subtle shadow
    ctx.globalAlpha = alpha * 0.3;
    ctx.beginPath();
    ctx.ellipse(x + 1, y + 2, r * 0.9, r * 0.6, 0, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(0,0,0,.25)";
    ctx.fill();

    ctx.restore();
}

function render() {
    if (!READY) return;
    drawBoard();

    // Draw all placed stones
    for (let i = 0; i < SIZE; i++) {
        for (let j = 0; j < SIZE; j++) {
            const v = board[i][j];
            if (v !== 0) drawStone(i, j, v, 1);
        }
    }

    // Draw hover preview only when it's user's turn and game hasn't ended
    if (!GAME_ENDED && hover.valid && hover.i !== null && hover.j !== null) {
        const isUserTurn = (USER_COLOR === 'black' && turn === 1) ||
            (USER_COLOR === 'white' && turn === 2);

        if (isUserTurn && board[hover.i][hover.j] === 0) {
            drawStone(hover.i, hover.j, turn, 0.5);
        }
    }
}

async function sendPass() {
    if (GAME_ENDED) {
        showMsg("Game has ended - cannot pass");
        return;
    }

    const btn = document.getElementById("pass");
    btn.disabled = true;
    showMsg("Passing turn…");
    try {
        const res = await fetch(`/game/pass/${BOARD_ID}`, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": CSRF_TOKEN }
        });
        const payload = await res.json().catch(() => ({}));
        if (!res.ok || payload.error) {
            showMsg(payload.message || "Pass rejected");
            return;
        }

        // Check if game ended
        if (payload.data && payload.data.game_ended) {
            GAME_ENDED = true;
            TERRITORY = payload.data.territory;
            SCORE = payload.data.score;
            WINNER = payload.data.score?.winner;
            updateGameEndedUI();
            render(); // Re-render to show territories
        }

        clearMsg();
    } catch {
        showMsg("Network error");
    } finally {
        if (!GAME_ENDED) {
            btn.disabled = false;
        }
    }
}

// Event handlers
function getMousePos(evt) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / dpr / rect.width;
    const scaleY = canvas.height / dpr / rect.height;
    const x = (evt.clientX - rect.left) * scaleX;
    const y = (evt.clientY - rect.top) * scaleY;
    return { x, y };
}

canvas.addEventListener("mousemove", (e) => {
    if (GAME_ENDED) return;
    const { x, y } = getMousePos(e);
    const hit = pxToCoord(x, y);
    hover = hit;
    render();
});

canvas.addEventListener("mouseleave", () => {
    hover = { i: null, j: null, valid: false };
    render();
});

canvas.addEventListener("click", async (e) => {
    if (GAME_ENDED) {
        showMsg("Game has ended - no more moves allowed");
        return;
    }

    const isUserTurn = (USER_COLOR === 'black' && turn === 1) ||
        (USER_COLOR === 'white' && turn === 2);

    if (!isUserTurn) {
        showMsg("Not your turn!");
        return;
    }

    const { x, y } = getMousePos(e);
    const { i, j, valid } = pxToCoord(x, y);
    if (!valid) return;
    if (board[i][j] !== 0) return showMsg("Position occupied");

    try {
        await sendMove(i, j);
    } catch {
        showMsg("Network error");
    }
});

function updateTurnLabel() {
    const el = document.getElementById("turn-text");
    const stoneEl = document.getElementById("turn-stone");

    if (GAME_ENDED) {
        const winnerText = WINNER === 'black' ? 'Black' : 'White';
        el.textContent = `Winner: ${winnerText}`;
        stoneEl.className = WINNER === 'black' ? 'status-stone black-stone' : 'status-stone white-stone';
        el.style.color = '#10b981';
        el.style.fontWeight = '700';
        return;
    }

    const turnColor = turn === 1 ? "Black" : "White";
    el.textContent = `Turn: ${turnColor}`;

    // Update stone indicator
    stoneEl.className = turn === 1 ? 'status-stone black-stone' : 'status-stone white-stone';

    // Highlight when it's user's turn
    const isUserTurn = (USER_COLOR === 'black' && turn === 1) ||
        (USER_COLOR === 'white' && turn === 2);

    if (isUserTurn) {
        el.style.color = '#667eea';
        el.style.fontWeight = '700';
    } else {
        el.style.color = '#2c3e50';
        el.style.fontWeight = '600';
    }
}

// Initialize
updateCanvasSize();
loadBoard();
document.getElementById("pass").addEventListener("click", sendPass);

// Handle window resize with debouncing
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        updateCanvasSize();
        render();
    }, 150);
});

// WebSocket for live updates
(function () {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${scheme}://${location.host}/ws/board/${BOARD_ID}/`;
    let ws;
    let backoff = 500;

    function connect() {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            backoff = 500;
        };

        ws.onmessage = () => {
            loadBoard().catch(() => { });
        };

        ws.onerror = () => {
            try { ws.close(); } catch { }
        };

        ws.onclose = () => {
            if (document.visibilityState !== "hidden") {
                setTimeout(connect, backoff);
                backoff = Math.min(backoff * 2, 5000);
            }
        };
    }

    window.addEventListener("beforeunload", () => {
        try {
            if (ws && ws.readyState === WebSocket.OPEN) ws.close(1001);
        } catch { }
    });

    connect();
})();