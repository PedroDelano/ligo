let SIZE = 19;                 // will be updated from server
const board = [];              // 0 empty, 1 black, 2 white
for (let i = 0; i < SIZE; i++) board.push(Array(SIZE).fill(0));
let turn = 1;                  // 1 black, 2 white
let READY = false;

const CELL = 30;           // px between lines
const PADDING = 20;        // outer margin
const W = PADDING * 2 + CELL * (SIZE - 1);
const H = W;
const meta = document.getElementById("meta");
const BOARD_ID = Number(meta.dataset.boardId);
const canvas = document.getElementById("board");
const ctx = canvas.getContext("2d");
const dpr = Math.max(1, window.devicePixelRatio || 1);
canvas.style.width = W + "px";
canvas.style.height = H + "px";
canvas.width = Math.round(W * dpr);
canvas.height = Math.round(H * dpr);
ctx.scale(dpr, dpr);
let hover = { i: null, j: null, valid: false };
const CSRF_TOKEN = (() => {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
})();


// function getCsrfToken() {
//     const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
//     return m ? decodeURIComponent(m[1]) : "";
// }

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

    const moves = Array.isArray(payload.moves) ? payload.moves : [];
    if (!payload.first_move && moves.length) {
        for (const mv of moves) {
            const color = mv.color === "B" ? 1 : 2;
            board[mv.x][mv.y] = color;
        }
    }
    turn = payload.next_color === "B" ? 1 : 2;
    updateTurnLabel();
    READY = true;
    render();
}


async function sendMove(i, j) {
    const colorChar = (turn === 1 ? "B" : "W");
    const res = await fetch(`/game/place/${BOARD_ID}/${i}/${j}/${colorChar}/`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": CSRF_TOKEN }
    });

    const payload = await res.json();
    if (!res.ok || payload.error) {
        showMsg(payload.message || "Move rejected");
        return;
    }
    await loadBoard();
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
    }
}

function drawStone(i, j, color, alpha = 1) {
    const { x, y } = coordToPx(i, j);
    const r = Math.floor(CELL * 0.44);
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

    board[i][j] = turn;
    updateTurnLabel();
    render();

    try {
        await sendMove(i, j);
        clearMsg();
    } catch {
        showMsg("Network error");
    }
});

function updateTurnLabel() {
    const el = document.getElementById("turn");
    el.textContent = `Turn: ${turn === 1 ? "Black ●" : "White ○"}`;
}

// Call this once after setting up canvas and drawing helpers:
loadBoard();
