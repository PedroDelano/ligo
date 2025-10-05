import logging
import os
import subprocess
import threading
from queue import Empty, Queue
from typing import Optional, Tuple

from bot.engines.base import BotEngine
from settings import settings

logger = logging.getLogger(__name__)

DIFFICULTY_CONFIG = {
    "simple": {"threads": 4, "max_tree_size": 256, "thinking_time": 3},
    "intermediate": {"threads": 4, "max_tree_size": 512, "thinking_time": 7},
    "advanced": {"threads": 4, "max_tree_size": 2048, "thinking_time": 20},
}


class PachiGTPEngine:
    """Manages a single Pachi engine process"""

    def __init__(
        self,
        threads: int,
        max_tree_size: int,
        thinking_time: int,
        pachi_path=settings.PACHI_PATH,
    ):
        assert isinstance(threads, int)
        assert isinstance(max_tree_size, int)
        assert isinstance(pachi_path, str)
        assert os.path.isfile(pachi_path)
        assert threads > 0
        assert max_tree_size > 32
        assert thinking_time > 0

        """Initialize Pachi engine subprocess"""
        args = [
            pachi_path,
            f"threads={threads}",
            f"max_tree_size={max_tree_size}",
            "-t",
            str(thinking_time),
        ]

        logger.debug(f"Starting engine with {' '.join(args)}")

        self.process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.lock = threading.Lock()
        self.initialization_complete = threading.Event()

        # Start thread to continuously read stderr (to prevent blocking)
        self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self.stderr_thread.start()
        self._wait_for_initialization()

        logger.info(f"Started Pachi engine with {threads} threads")

    def _read_stderr(self):
        """Continuously read stderr to prevent blocking and detect initialization"""
        try:
            while self.process.poll() is None:
                line = self.process.stderr.readline()
                if line:
                    line_stripped = line.strip()
                    logger.debug(f"Pachi stderr: {line_stripped}")

                    # Check for initialization completion marker
                    if not self.initialization_complete.is_set():
                        if (
                            "overrides" in line_stripped.lower()
                            and "loaded" in line_stripped.lower()
                        ):
                            logger.info(
                                f"Pachi initialization complete: {line_stripped}"
                            )
                            self.initialization_complete.set()
        except Exception as e:
            logger.debug(f"stderr thread ended: {e}")

    def _wait_for_initialization(self, timeout=15.0):
        """Wait for Pachi to complete initialization"""
        logger.info("Waiting for Pachi initialization...")

        if self.initialization_complete.wait(timeout=timeout):
            logger.info("Pachi engine ready")
        else:
            logger.warning(
                f"Pachi initialization marker not seen within {timeout}s, proceeding anyway"
            )
            # Check if process is still alive
            if not self.is_alive():
                raise RuntimeError("Pachi process died during initialization")

    def send_command(self, command):
        """Send a GTP command and get response (thread-safe)"""
        with self.lock:
            try:
                if not self.is_alive():
                    logger.error(f"Process died before sending command: {command}")
                    return None

                self.process.stdin.write(command + "\n")
                self.process.stdin.flush()
                response_lines = []

                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        logger.error(
                            f"Unexpected EOF while reading response for: {command}"
                        )
                        return None

                    line = line.rstrip("\n")
                    if not line:
                        break
                    response_lines.append(line)

                response = "\n".join(response_lines)

                # Check for error
                if response.startswith("?"):
                    logger.error(f"GTP Error for '{command}': {response}")
                    return None

                # Remove success prefix
                if response.startswith("="):
                    result = response[1:].strip()
                    return result if result else ""

                return response.strip()

            except BrokenPipeError as e:
                logger.error(f"Broken pipe sending command '{command}': {e}")
                # Check stderr for any error messages
                try:
                    stderr_output = self.process.stderr.read()
                    if stderr_output:
                        logger.error(f"Pachi stderr: {stderr_output}")
                except Exception:
                    pass
                return None
            except Exception as e:
                logger.error(f"Error sending command '{command}': {e}")
                return None

    def set_boardsize(self, size):
        """Set board size"""
        return self.send_command(f"boardsize {size}")

    def clear_board(self):
        """Clear the board"""
        return self.send_command("clear_board")

    def set_komi(self, komi):
        """Set komi value"""
        return self.send_command(f"komi {komi}")

    def play_move(self, color, move):
        """Play a move. color: 'black' or 'white', move: GTP coordinate"""
        return self.send_command(f"play {color} {move}")

    def generate_move(self, color):
        """
        Generate a move for the given color.
        time_limit: optional time limit in seconds
        """
        result = self.send_command(f"genmove {color}")
        return result

    def is_alive(self):
        """Check if engine process is still running"""
        return self.process.poll() is None

    def quit(self):
        """Quit the engine"""
        try:
            if self.is_alive():
                self.send_command("quit")
                self.process.wait(timeout=2)
        except Exception:
            if self.is_alive():
                self.process.kill()

    def __del__(self):
        """Cleanup"""
        if hasattr(self, "process") and self.process.poll() is None:
            self.quit()


class PachiEnginePool:
    """Thread-safe pool of Pachi engines for concurrent access"""

    def __init__(self, difficulty: str, pachi_path: str, pool_size: int = 3):
        """
        Initialize engine pool.
        pool_size: number of engine instances to maintain
        """
        self.difficulty = difficulty
        self.pachi_path = pachi_path
        self.pool_size = pool_size
        self.config = self._get_config(difficulty)

        # Queue of available engines
        self.available_engines = Queue(maxsize=pool_size)
        self.all_engines = []
        self.lock = threading.Lock()

        # Pre-create engines
        for _ in range(pool_size):
            engine = self._create_engine()
            if engine:
                self.available_engines.put(engine)
                self.all_engines.append(engine)

        logger.info(
            f"Created engine pool for {difficulty} with {len(self.all_engines)} instances"
        )

    def _get_config(self, difficulty):
        """Get configuration for difficulty level"""
        assert isinstance(difficulty, str)
        assert difficulty in DIFFICULTY_CONFIG.keys()
        return DIFFICULTY_CONFIG.get(difficulty)

    def _create_engine(self):
        """Create a new engine instance"""
        try:
            return PachiGTPEngine(
                threads=self.config["threads"],
                max_tree_size=self.config["max_tree_size"],
                thinking_time=self.config["thinking_time"],
            )
        except Exception as e:
            logger.error(f"Failed to create engine: {e}")
            return None

    def acquire(self, timeout=30):
        """
        Get an engine from the pool.
        Blocks until an engine is available or timeout.
        """
        try:
            engine = self.available_engines.get(timeout=timeout)

            # Check if engine is still alive
            if not engine.is_alive():
                logger.warning("Dead engine detected, creating new one")
                with self.lock:
                    if engine in self.all_engines:
                        self.all_engines.remove(engine)
                    new_engine = self._create_engine()
                    if new_engine:
                        self.all_engines.append(new_engine)
                        engine = new_engine
                    else:
                        logger.error("Failed to create replacement engine")
                        return None

            return engine
        except Empty:
            logger.error(f"Timeout waiting for engine from pool ({self.difficulty})")
            return None

    def release(self, engine):
        """Return an engine to the pool"""
        if engine and engine.is_alive():
            self.available_engines.put(engine)
        else:
            logger.warning("Not returning dead engine to pool")

    def cleanup(self):
        """Clean up all engines in pool"""
        with self.lock:
            for engine in self.all_engines:
                try:
                    engine.quit()
                except Exception as e:
                    logger.error(f"Error quitting engine: {e}")
            self.all_engines.clear()

            # Clear the queue
            while not self.available_engines.empty():
                try:
                    self.available_engines.get_nowait()
                except Empty:
                    break

        logger.info(f"Cleaned up engine pool: {self.difficulty}")


class PachiBot(BotEngine):
    """Pachi-powered bot implementation with engine pooling"""

    # Class-level pools (one pool per difficulty)
    _pools = {}
    _pools_lock = threading.Lock()

    # Difficulty configurations

    def __init__(
        self,
        board_size: int,
        difficulty: str,
        pachi_path=settings.PACHI_PATH,
        pool_size=settings.PACHI_POOL_SIZE,
    ):
        super().__init__(board_size, difficulty)
        self.pachi_path = pachi_path
        self.pool_size = pool_size
        self._ensure_pool_exists()

    def _ensure_pool_exists(self):
        """Ensure engine pool exists for this difficulty"""
        with self._pools_lock:
            if self.difficulty not in self._pools:
                pool = PachiEnginePool(
                    difficulty=self.difficulty,
                    pachi_path=self.pachi_path,
                    pool_size=self.pool_size,
                )
                self._pools[self.difficulty] = pool
                logger.info(f"Created new engine pool for: {self.difficulty}")

    def _setup_game_state(self, engine, game_state: dict):
        """Set up the engine with current game state"""
        board_size = game_state["board_size"]
        moves = game_state["moves"]

        # Reset board
        engine.set_boardsize(board_size)
        engine.clear_board()
        engine.set_komi(7.5)  # Standard komi

        # Replay all moves
        for move in moves:
            if move["x"] == -1:  # Pass move
                continue

            gtp_move = self._coords_to_gtp(move["x"], move["y"], board_size)
            color = "black" if move["color"] == "B" else "white"

            result = engine.play_move(color, gtp_move)
            if result is None:
                logger.warning(f"Failed to play move: {color} {gtp_move}")

    def _coords_to_gtp(self, x: int, y: int, board_size: int) -> str:
        """
        Convert 0-indexed (x, y) to GTP format.
        Assumes your board uses (0,0) at top-left.
        GTP uses columns A-T (skip I) and rows 1-19 from bottom.
        """
        col_letters = "ABCDEFGHJKLMNOPQRST"  # No 'I'
        col = col_letters[x]

        # Convert row: flip y-axis (GTP counts from bottom)
        row = board_size - y

        return f"{col}{row}"

    def _gtp_to_coords(self, gtp_move: str, board_size: int) -> Tuple[int, int]:
        """Convert GTP format to 0-indexed (x, y)"""
        if not gtp_move or gtp_move.lower() in ["pass", "resign"]:
            return (-1, -1)

        col_letters = "ABCDEFGHJKLMNOPQRST"
        col = col_letters.index(gtp_move[0].upper())
        row = int(gtp_move[1:])

        # Flip y-axis
        y = board_size - row

        return (col, y)

    def select_move(self, game_state: dict) -> Optional[Tuple[int, int]]:
        """
        Select next move using Pachi.
        Returns (x, y) for next move, or None to pass.
        Thread-safe: acquires engine from pool.
        """
        pool = self._pools.get(self.difficulty)
        if not pool:
            logger.error(f"No engine pool for difficulty: {self.difficulty}")
            return None

        # Acquire engine from pool
        engine = pool.acquire(timeout=30)
        if not engine:
            logger.error("Failed to acquire engine from pool")
            return None

        try:
            # Set up game state in engine
            self._setup_game_state(engine, game_state)

            # Determine which color to play
            moves = game_state["moves"]
            next_color = "black" if len(moves) % 2 == 0 else "white"

            # Generate move
            gtp_move = engine.generate_move(next_color)

            if not gtp_move or gtp_move.lower() in ["pass", "resign"]:
                logger.info(f"Pachi decided to pass/resign: {gtp_move}")
                return None

            # Convert to coordinates
            x, y = self._gtp_to_coords(gtp_move, game_state["board_size"])
            logger.info(f"Pachi selected move: {gtp_move} -> ({x}, {y})")

            return (x, y)

        except Exception as e:
            logger.error(f"Error in PachiBot.select_move: {e}", exc_info=True)
            return None

        finally:
            # ALWAYS return engine to pool
            pool.release(engine)

    def should_pass(self, game_state: dict) -> bool:
        """Pachi decides itself whether to pass via genmove"""
        return False

    @classmethod
    def cleanup_pools(cls):
        """Clean up all engine pools"""
        with cls._pools_lock:
            for difficulty, pool in cls._pools.items():
                try:
                    pool.cleanup()
                    logger.info(f"Cleaned up pool: {difficulty}")
                except Exception as e:
                    logger.error(f"Error cleaning up pool {difficulty}: {e}")
            cls._pools.clear()
