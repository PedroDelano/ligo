let SIZE = 19;                 // will be updated from server
const board = [];              // 0 empty, 1 black, 2 white
for (let i = 0; i < SIZE; i++) board.push(Array(SIZE).fill(0));
let turn = 1;                  // 1 black, 2 white
let READY = false;

let CELL = 30;           // px between lines (will be calculated)
const PADDING = 20;        // outer margin

const meta = document.getElementById("meta");
const BOARD_ID = Number(meta.dataset.boardId);
const canvas = document.getElementById("board");
const ctx = canvas.getContext("2d");
const dpr = Math.max(1, window.devicePixelRatio || 1);

let hover = { i: null, j: null, valid: false };
const CSRF_TOKEN = (() => {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
})();

// Calculate optimal cell size based on container width
function calculateCellSize() {
    const container = document.querySelector('.wrap');
    const maxWidth = Math.min(container.clientWidth - 48, 620); // 48px for padding, max 620
    const availableSpace = maxWidth - (PADDING * 2);
    CELL = Math.floor(availableSpace / (SIZE - 1));
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
    calculateCellSize(); // Recalculate cell size based on container
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
    updateTurnLabel();
    READY = true;
    render();
    clearMsg();
}

async function sendMove(i, j) {
    const colorChar = (turn === 1 ? "B" : "W");
    const res = await fetch(`/game/place/${BOARD_ID}/${i}/${j}/`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": CSRF_TOKEN }
    });

    const payload = await res.json();
    if (!res.ok || payload.error) {
        showMsg(payload.message || "Move rejected");
        return;
    }
    // await loadBoard();
    clearMsg();
}

function showMsg(s) {
    const m = document.getElementById("msg");
    m.textContent = s;
}
function clearMsg() {
    const m = document.getElementById("msg");
    m.textContent = "";
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

    // background wood grain hint
    ctx.clearRect(0, 0, W, H);

    // subtle wood texture lines
    ctx.fillStyle = "#d6b26b";
    ctx.fillRect(0, 0, W, H);

    // grid
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

    // star points for 19x19
    if (SIZE === 19) {
        const stars = [3, 9, 15];
        ctx.fillStyle = "#443014";
        for (const i of stars) {
            for (const j of stars) {
                const { x, y } = coordToPx(i, j);
                ctx.beginPath();
                ctx.arc(x, y, 2.5, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    } else if (SIZE === 13) {
        // star points for 13x13 (3-3, 3-9, 9-3, 9-9, and center at 6-6)
        const stars = [3, 6, 9];
        ctx.fillStyle = "#443014";
        for (const i of stars) {
            for (const j of stars) {
                const { x, y } = coordToPx(i, j);
                ctx.beginPath();
                ctx.arc(x, y, 2.5, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    } else if (SIZE === 9) {
        // star points for 9x9 (2-2, 2-6, 6-2, 6-6, and center at 4-4)
        const stars = [2, 4, 6];
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

    // the move was passed
    if (x == -1 || y == -1) return;

    ctx.save();
    ctx.globalAlpha = alpha;

    // stone base
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.closePath();

    if (color === 1) {
        // black stone with simple light
        const grad = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, r * 0.1, x, y, r);
        grad.addColorStop(0, "#666");
        grad.addColorStop(1, "#111");
        ctx.fillStyle = grad;
        ctx.fill();
    } else {
        // white stone with shadow ring
        ctx.fillStyle = "#f7f7f7";
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,.2)";
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    // subtle drop shadow
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
    for (let i = 0; i < SIZE; i++) {
        for (let j = 0; j < SIZE; j++) {
            const v = board[i][j];
            if (v !== 0) drawStone(i, j, v, 1);
        }
    }
    if (hover.valid && hover.i !== null && hover.j !== null) {
        if (board[hover.i][hover.j] === 0) {
            drawStone(hover.i, hover.j, turn, 0.5);
        }
    }
}

async function sendPass() {
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
        // await loadBoard();       // refresh size/turn/moves
        clearMsg();              // or showMsg("You passed.");
    } catch {
        showMsg("Network error");
    } finally {
        btn.disabled = false;
    }
}

// Events
function getMousePos(evt) {
    const rect = canvas.getBoundingClientRect();
    const x = (evt.clientX - rect.left);
    const y = (evt.clientY - rect.top);
    return { x, y };
}

canvas.addEventListener("mousemove", (e) => {
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
    const el = document.getElementById("turn");
    el.textContent = `Turn: ${turn === 1 ? "Black ●" : "White ○"}`;
}

// Initialize canvas size and load board
updateCanvasSize();
loadBoard();
document.getElementById("pass").addEventListener("click", sendPass);

// Handle window resize
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        updateCanvasSize();
        render();
    }, 150);
});

// --- Live updates via WebSocket ---
(function () {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${scheme}://${location.host}/ws/board/${BOARD_ID}/`;
    let ws;
    let backoff = 500; // ms (will double up to 5s)

    function connect() {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            backoff = 500; // reset on successful connect
            // console.debug("WS connected");
        };

        ws.onmessage = (e) => {
            // We just refresh from the server (simple & robust):
            // server can send {"event":"move"} or any payload; we don't rely on shape here
            loadBoard().catch(() => { });
        };

        ws.onerror = () => {
            // let onclose handle the retry
            try { ws.close(); } catch { }
        };

        ws.onclose = () => {
            // Reconnect with exponential backoff while tab is visible
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
