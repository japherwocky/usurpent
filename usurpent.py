import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado import websocket
from tornado.log import enable_pretty_logging
from dotenv import load_dotenv
from typing import Any

import config
import protocol
import db

import os
import logging
import math
import random
import json
import re
import time
from collections import defaultdict

# Load environment variables from .env file
load_dotenv()

from models import Account


# --- Auth input validation (mirrors pearachute's field caps) -------------
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_username(username):
    return isinstance(username, str) and bool(_USERNAME_RE.match(username))


def _valid_password(password):
    return isinstance(password, str) and len(password) >= 8


def _valid_email(email):
    return isinstance(email, str) and len(email) <= 320 and bool(_EMAIL_RE.match(email))


class RateLimiter:
    """In-memory, per-process throttle (mirrors pearachute's contact form).

    Resets on restart and does not span multiple workers; it exists to blunt
    a script, not to be an authority.
    """

    def __init__(self, max_events, window):
        self.max_events = max_events
        self.window = window
        self._hits = defaultdict(list)

    def check(self, key):
        now = time.time()
        recent = [t for t in self._hits[key] if now - t < self.window]
        self._hits[key] = recent
        if len(recent) >= self.max_events:
            return False
        recent.append(now)
        return True


def _set_security_headers(handler):
    """Apply consistent security headers to a RequestHandler response."""
    handler.set_header("X-Content-Type-Options", "nosniff")
    handler.set_header("X-Frame-Options", "DENY")
    handler.set_header("X-XSS-Protection", "1; mode=block")
    handler.set_header("Referrer-Policy", "strict-origin-when-cross-origin")
    handler.set_header(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'",
    )
    # HSTS only in production (HTTPS).
    if not handler.application.settings.get("debug"):
        handler.set_header(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )


WEB_DIST = os.path.join(os.path.dirname(__file__), "web", "dist")


class BaseHandler(tornado.web.RequestHandler):
    """Base handler with security headers"""

    def set_default_headers(self):
        _set_security_headers(self)

    @property
    def current_account(self):
        """The logged-in Account, or None for a guest/anonymous session."""
        raw = self.get_secure_cookie("user")
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            account_id = int(raw)
        except (ValueError, TypeError):
            return None
        return Account.get_or_none(Account.id == account_id)

    def write_error(self, status_code, **kwargs):
        """Errors are JSON here, not Tornado's HTML page (mirrors pearachute)."""
        reason = "Something went wrong."
        exc_info = kwargs.get("exc_info")
        if exc_info and isinstance(exc_info[1], tornado.web.HTTPError):
            reason = exc_info[1].log_message or reason
        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps({"error": reason}))


def _wrap_angle(angle):
    """Normalize an angle to (-pi, pi]."""
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle <= -math.pi:
        angle += 2 * math.pi
    return angle


def _girth_for_score(score):
    """Body radius (world units) for a given life score, capped."""
    return min(config.MAX_GIRTH, config.BASE_GIRTH + score * config.GIRTH_PER_FOOD)


def _value_for_radius(radius):
    """Pellet value from its radius: bigger pellets are worth more."""
    return max(1, round(radius / config.FOOD_RADIUS_PER_VALUE))


class Player:
    """One snake on the map. Server-authoritative state only."""

    def __init__(self, player_id, handler, x, y):
        self.id = player_id
        self.handler = handler
        # Account linkage: None for anonymous guests. Used by #179 to persist
        # stats back to the Account row on death/disconnect.
        self.account_id = getattr(handler, "account_id", None)
        self.username = getattr(handler, "username", None)
        # Food eaten across this whole session (all lives); persists across
        # respawns. Per-life score lives in self.score (reset on respawn).
        self.session_food = 0
        self.respawn(x, y)

    def respawn(self, x, y):
        """Reset to a live snake at (x, y). Used on spawn and after death."""
        self.x = x
        self.y = y
        self.heading = random.uniform(-math.pi, math.pi)
        # Initial steering direction matches the spawn heading so the snake
        # sets off straight. Clients later send a direction vector (dx, dy).
        self.target = (math.cos(self.heading), math.sin(self.heading))
        self.alive = True
        self.score = 0
        # New life: not yet persisted. session_food is intentionally kept so
        # food from prior lives in this session still counts.
        self.life_persisted = False
        self.length = config.INITIAL_TAIL_LENGTH
        self.girth = _girth_for_score(0)
        # Seed the trail as a line behind the head so it renders as a snake.
        back_x = -math.cos(self.heading)
        back_y = -math.sin(self.heading)
        self.points = [
            (x + back_x * i * config.TAIL_SEGMENT_SPACING,
             y + back_y * i * config.TAIL_SEGMENT_SPACING)
            for i in range(self.length)
        ]

    def set_target(self, x, y):
        self.target = (x, y)

    def step(self, dt):
        """Advance one tick toward the mouse target, capped turn rate."""
        if not self.alive:
            return
        tx, ty = self.target
        if tx == 0 and ty == 0:
            desired = self.heading  # no input: keep going straight
        else:
            desired = math.atan2(ty, tx)  # target is a direction vector
        diff = _wrap_angle(desired - self.heading)
        max_step = config.MAX_TURN_RATE * dt
        self.heading += max(-max_step, min(max_step, diff))

        self.x += math.cos(self.heading) * config.HEAD_SPEED * dt
        self.y += math.sin(self.heading) * config.HEAD_SPEED * dt
        self.x = max(0.0, min(config.MAP_WIDTH, self.x))
        self.y = max(0.0, min(config.MAP_HEIGHT, self.y))

        last_x, last_y = self.points[-1]
        if math.hypot(self.x - last_x, self.y - last_y) >= config.TAIL_SEGMENT_SPACING:
            self.points.append((self.x, self.y))
            while len(self.points) > self.length:
                self.points.pop(0)

    def to_dict(self):
        return {
            protocol.FIELD_ID: self.id,
            protocol.FIELD_X: round(self.x, 2),
            protocol.FIELD_Y: round(self.y, 2),
            protocol.FIELD_HEADING: round(self.heading, 4),
            protocol.FIELD_POINTS: [[round(px, 2), round(py, 2)] for px, py in self.points],
            protocol.FIELD_ALIVE: self.alive,
            protocol.FIELD_SCORE: self.score,
            protocol.FIELD_GIRTH: round(self.girth, 2),
            protocol.FIELD_USERNAME: self.username,
        }


class World:
    """Authoritative game state, ticked at a fixed rate."""

    def __init__(self):
        self.players = {}  # player_id -> Player
        self.foods = {}    # food_id -> (x, y)
        self._next_id = 0
        self._food_next = 0
        self.tick_count = 0
        self._food_spawn_acc = 0.0  # accumulator for timed food spawning
        self._callback = None
        for _ in range(config.FOOD_COUNT):
            self._spawn_food()

    def start(self):
        """Begin the simulation loop on the current IOLoop."""
        interval_ms = 1000.0 / config.TICK_HZ
        self._callback = tornado.ioloop.PeriodicCallback(self.tick, interval_ms)
        self._callback.start()

    def stop(self):
        if self._callback is not None:
            self._callback.stop()

    def _make_food(self, x, y, radius, value, dropped):
        """Store one pellet. Foods are dicts so per-pellet radius/value/dropped
        can vary (spawned vs. carcass)."""
        self._food_next += 1
        fid = str(self._food_next)
        self.foods[fid] = {
            "x": x,
            "y": y,
            "r": radius,
            "value": value,
            "dropped": dropped,
        }

    def _spawn_food(self):
        # Spawn inside a circle centered on the map so new food appears in a
        # consistent, discoverable region (the client draws its border).
        cx = config.MAP_WIDTH / 2.0
        cy = config.MAP_HEIGHT / 2.0
        r = config.FOOD_SPAWN_RADIUS * math.sqrt(random.random())
        theta = random.uniform(0.0, 2.0 * math.pi)
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        radius = config.FOOD_BASE_RADIUS
        self._make_food(x, y, radius, _value_for_radius(radius), False)

    def spawn_player(self, handler):
        self._next_id += 1
        player_id = str(self._next_id)
        x, y = self._free_spot()
        player = Player(player_id, handler, x, y)
        self.players[player_id] = player
        handler.player_id = player_id
        logging.info(f"Player {player_id} spawned (total: {len(self.players)})")
        handler.write_message(self._welcome(player_id, player))
        self._broadcast_snapshot()
        return player_id

    def remove_player(self, player_id):
        player = self.players.get(player_id)
        if player is not None:
            # Persist the current life if it had not already been recorded
            # at death (i.e. the player disconnected while still alive).
            self._persist_life(player)
        self.players.pop(player_id, None)
        logging.info(f"Player {player_id} removed (total: {len(self.players)})")
        self._broadcast_snapshot()

    def tick(self):
        dt = 1.0 / config.TICK_HZ
        self.tick_count += 1
        for player in self.players.values():
            player.step(dt)
        self._spawn_timer(dt)
        self._handle_food()
        self._handle_collisions()
        self._broadcast_snapshot()

    def _spawn_timer(self, dt):
        """Drop new food on a fixed interval to keep the world stocked."""
        self._food_spawn_acc += dt
        if self._food_spawn_acc >= config.FOOD_SPAWN_INTERVAL:
            self._food_spawn_acc -= config.FOOD_SPAWN_INTERVAL
            if len(self.foods) < config.FOOD_MAX:
                self._spawn_food()

    def _free_spot(self):
        margin = config.INITIAL_TAIL_LENGTH * config.TAIL_SEGMENT_SPACING
        return (
            random.uniform(margin, config.MAP_WIDTH - margin),
            random.uniform(margin, config.MAP_HEIGHT - margin),
        )

    def _handle_food(self):
        for player in self.players.values():
            if not player.alive:
                continue
            for fid, food in list(self.foods.items()):
                fx, fy = food["x"], food["y"]
                if math.hypot(player.x - fx, player.y - fy) < (food["r"] + config.FOOD_PICKUP_PAD):
                    del self.foods[fid]
                    player.score += food["value"]
                    player.length += food["value"] * config.FOOD_GROWTH
                    player.session_food += 1
                    player.girth = _girth_for_score(player.score)

    def _handle_collisions(self):
        for player in self.players.values():
            if not player.alive:
                continue
            # World border: die on contact rather than sliding along the edge
            # (which made steering feel stuck). The head is clamped in step(),
            # so reaching the bound means it is exactly at the wall.
            if (player.x <= 0.0 or player.x >= config.MAP_WIDTH or
                    player.y <= 0.0 or player.y >= config.MAP_HEIGHT):
                self._kill_player(player)
                continue
            for other in self.players.values():
                if other is player or not other.alive:
                    continue
                # Die if the head enters (attacker girth + defender girth) of
                # any body point. Bigger snakes are both bulkier and easier to
                # clip, so girth matters in both directions.
                hit = any(
                    math.hypot(player.x - px, player.y - py)
                    < (player.girth + other.girth)
                    for (px, py) in other.points
                )
                if hit:
                    self._kill_player(player)
                    break

    def _kill_player(self, player):
        player.alive = False
        logging.info(f"Player died (score {player.score})")
        # Leave a carcass of food where the body fell, then record stats.
        self._drop_carcass(player)
        self._persist_life(player)
        tornado.ioloop.IOLoop.current().call_later(
            config.RESPAWN_DELAY, self._respawn_player, player.id
        )

    def _drop_carcass(self, player):
        """Scatter food pellets along the dead serpent's body -- one per
        segment, sized from its girth. Dropped pellets render at low opacity."""
        drop_r = player.girth * config.DROP_RADIUS_FACTOR
        value = _value_for_radius(drop_r)
        pts = player.points
        # One pellet per segment; if the carcass is enormous, sample evenly so
        # we don't flood the world with food.
        if len(pts) > config.CARCASS_MAX_PELLETS:
            step = len(pts) / config.CARCASS_MAX_PELLETS
            indices = range(0, len(pts), max(1, int(step)))
        else:
            indices = range(len(pts))
        for i in indices:
            px, py = pts[i]
            self._make_food(px, py, drop_r, value, True)

    def _persist_life(self, player):
        """Write one life's stats to the linked Account (no-op for guests).

        Guarded by `life_persisted` so a death-then-disconnect (or repeated
        calls) only records the life once.
        """
        if player.account_id is None or player.life_persisted:
            return
        account = Account.get_or_none(Account.id == player.account_id)
        if account is None:
            player.life_persisted = True
            return
        account.games_played += 1
        account.high_score = max(account.high_score, player.score)
        account.total_food += player.score
        account.save()
        player.life_persisted = True

    def _respawn_player(self, player_id):
        player = self.players.get(player_id)
        if player is None or player.alive:
            return
        x, y = self._free_spot()
        player.respawn(x, y)
        logging.info(f"Player {player_id} respawned")

    def _food_list(self):
        return [
            {protocol.FIELD_ID: fid,
             protocol.FIELD_X: round(f["x"], 2),
             protocol.FIELD_Y: round(f["y"], 2),
             protocol.FIELD_FOOD_RADIUS: round(f["r"], 2),
             protocol.FIELD_FOOD_DROPPED: f["dropped"]}
            for fid, f in self.foods.items()
        ]

    def _snapshot(self):
        return {
            protocol.FIELD_TYPE: protocol.TYPE_SNAPSHOT,
            protocol.FIELD_TICK: self.tick_count,
            protocol.FIELD_PLAYERS: [p.to_dict() for p in self.players.values()],
            protocol.FIELD_FOOD: self._food_list(),
        }

    def _welcome(self, self_id, player):
        return {
            protocol.FIELD_TYPE: protocol.TYPE_WELCOME,
            protocol.FIELD_SELF_ID: self_id,
            protocol.FIELD_GUEST: player.account_id is None,
            protocol.FIELD_USERNAME: player.username,
            protocol.FIELD_MAP_WIDTH: config.MAP_WIDTH,
            protocol.FIELD_MAP_HEIGHT: config.MAP_HEIGHT,
            protocol.FIELD_HEAD_SPEED: config.HEAD_SPEED,
            protocol.FIELD_MAX_TURN_RATE: config.MAX_TURN_RATE,
            protocol.FIELD_TAIL_SPACING: config.TAIL_SEGMENT_SPACING,
            protocol.FIELD_TICK_HZ: config.TICK_HZ,
            protocol.FIELD_FOOD_SPAWN_RADIUS: config.FOOD_SPAWN_RADIUS,
            protocol.FIELD_PLAYERS: [p.to_dict() for p in self.players.values()],
            protocol.FIELD_FOOD: self._food_list(),
        }

    def _broadcast_snapshot(self):
        snapshot = self._snapshot()
        for player in self.players.values():
            if player.handler is not None:
                player.handler.write_message(snapshot)


class GameWebSocketHandler(BaseHandler, websocket.WebSocketHandler):
    """Real-time game connection.

    Spawns a Player on connect, accepts mouse-target input, and receives
    20 Hz snapshots from the World. Food, growth, collisions, and
    death/respawn are handled server-side in World.
    """

    application: "App"

    def open(self, *args, **kwargs):
        self.player_id = None
        # Bind to the logged-in account when a session cookie is present;
        # otherwise this is an anonymous guest (allowed to play). The cookie
        # is signed, so we trust it directly rather than re-authenticating.
        account = self.current_account
        self.account_id = account.id if account is not None else None
        self.username = account.username if account is not None else None
        self.application.world.spawn_player(self)

    def on_message(self, message):
        try:
            data = json.loads(message)
        except (ValueError, TypeError):
            logging.warning("Dropping malformed WS message")
            return
        if data.get(protocol.FIELD_TYPE) != protocol.TYPE_INPUT:
            return
        target = data.get(protocol.FIELD_TARGET)
        if not isinstance(target, dict):
            return
        player = self.application.world.players.get(self.player_id)
        if player is not None and player.alive:
            player.set_target(float(target[protocol.FIELD_X]),
                              float(target[protocol.FIELD_Y]))

    def on_close(self):
        player_id = getattr(self, "player_id", None)
        if player_id is not None:
            self.application.world.remove_player(player_id)

    def check_origin(self, origin):
        # Same-origin only for MVP. Tighten via settings if a proxy is added.
        return True


class AuthHandler(BaseHandler):
    """Base for JSON auth endpoints; errors are returned as JSON."""

    def _json_body(self):
        try:
            return json.loads(self.request.body or b"{}")
        except (ValueError, TypeError):
            return None

    def _set_session(self, account):
        self.set_secure_cookie(
            "user",
            str(account.id),
            httponly=True,
            secure=not self.application.settings.get("debug"),
            samesite="lax",
        )


class RegisterHandler(AuthHandler):
    """Create an account and start a session. POST only."""

    limiter = RateLimiter(max_events=5, window=3600)

    def post(self):
        if not self.limiter.check(self.request.remote_ip):
            self.set_status(429)
            self.write({"error": "Too many registration attempts. Try again later."})
            return

        body = self._json_body()
        if body is None:
            self.set_status(400)
            self.write({"error": "Invalid JSON body."})
            return

        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        email = (body.get("email") or "").strip() or None

        if not _valid_username(username):
            self.set_status(400)
            self.write({"error": "Username must be 3-32 chars: letters, numbers, _ or -."})
            return
        if not _valid_password(password):
            self.set_status(400)
            self.write({"error": "Password must be at least 8 characters."})
            return
        if email is not None and not _valid_email(email):
            self.set_status(400)
            self.write({"error": "Email address is not valid."})
            return
        if Account.select().where(Account.username == username).exists():
            self.set_status(409)
            self.write({"error": "Username already taken."})
            return
        if email is not None and Account.select().where(Account.email == email).exists():
            self.set_status(409)
            self.write({"error": "Email already registered."})
            return

        account = Account(username=username, email=email)
        account.set_password(password)
        account.save()
        self._set_session(account)
        self.write({"ok": True, "username": account.username})


class LoginHandler(AuthHandler):
    """Authenticate by username/password and start a session. POST only."""

    limiter = RateLimiter(max_events=10, window=3600)

    def post(self):
        if not self.limiter.check(self.request.remote_ip):
            self.set_status(429)
            self.write({"error": "Too many login attempts. Try again later."})
            return

        body = self._json_body()
        if body is None:
            self.set_status(400)
            self.write({"error": "Invalid JSON body."})
            return

        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        if not username or not password:
            self.set_status(400)
            self.write({"error": "Username and password are required."})
            return

        account = Account.get_or_none(Account.username == username)
        if account is None or not account.check_password(password):
            self.set_status(401)
            self.write({"error": "Invalid username or password."})
            return

        self._set_session(account)
        self.write({"ok": True, "username": account.username})


class LogoutHandler(AuthHandler):
    """End the current session. POST only."""

    def post(self):
        self.clear_cookie("user")
        self.write({"ok": True})


class SessionHandler(AuthHandler):
    """Report the current session: a registered account or a guest. GET only."""

    def get(self):
        account = self.current_account
        if account is None:
            self.write({"guest": True})
            return
        self.write({
            "guest": False,
            "username": account.username,
            "high_score": account.high_score,
            "games_played": account.games_played,
        })


class App (tornado.web.Application):
    world: World

    def __init__(self, debug=False):
        """
        Settings for our application
        """
        # Ensure the database and tables exist before serving anything.
        db.init_db()

        settings: dict[str, Any] = dict(
            cookie_secret=config.cookie_secret(debug=debug),
            xsrf_cookies=True,
            debug=debug,
        )

        handlers = [
            (r"/api/register$", RegisterHandler),
            (r"/api/login$", LoginHandler),
            (r"/api/logout$", LogoutHandler),
            (r"/api/me$", SessionHandler),
            (r"/ws", GameWebSocketHandler),
            (r"/(.*)", SpaStaticFileHandler, {"path": WEB_DIST, "default_filename": "index.html"}),
        ]

        super().__init__(handlers, **settings)
        self.world = World()
        self.world.start()


class SpaStaticFileHandler(tornado.web.StaticFileHandler):
    """Serve the built Svelte SPA, falling back to index.html.

    Unknown paths (client-side routes) resolve to index.html so the
    frontend router can handle them.
    """

    def initialize(self, path, default_filename="index.html"):
        tornado.web.StaticFileHandler.initialize(self, path, default_filename=default_filename)

    async def get(self, path, include_body=True):
        # Touching xsrf_token sets the _xsrf cookie, which the SPA reads back
        # out and echoes in the X-XSRFToken header when it POSTs. Without this
        # nothing ever sets the cookie, and every API POST is rejected.
        if not path.startswith(("assets/",)):
            self.xsrf_token
        await super().get(path, include_body)

    def set_default_headers(self):
        _set_security_headers(self)

    def validate_absolute_path(self, root, absolute_path):
        if not os.path.exists(absolute_path):
            # Client-side route or missing asset -> serve the app shell.
            default = self.default_filename or "index.html"
            absolute_path = os.path.join(root, default)
        return super().validate_absolute_path(root, absolute_path)


def main():
    from tornado.options import define, options
    define("port", default=int(os.getenv('PORT', 8011)), help="run on the given port", type=int)
    define("debug", default=os.getenv('DEBUG', 'False').lower() == 'true', help="run server in debug mode", type=bool)
    define("runtests", default=False, help="run tests", type=bool)

    tornado.options.parse_command_line()
    
    # Enable Tornado's pretty logging
    enable_pretty_logging()
    
    logging.info("Starting USURPENT server")
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        logging.warning("No .env file found. Using default configuration.")
        logging.info("Copy .env.example to .env and configure for production use.")

    if options.runtests:
        # put tests in the tests folder
        # Tests not implemented yet
        logging.info("Tests requested but not implemented yet")
        print("Tests not implemented yet. Please create tests/ directory first.")
        return

    try:
        http_server = tornado.httpserver.HTTPServer(App(debug=options.debug), xheaders=True)
        http_server.listen(options.port)
        
        logging.info(f"USURPENT server started on port {options.port}")
        logging.info(f"Access the application at: http://localhost:{options.port}/")
        
        tornado.ioloop.IOLoop.current().start()
        
    except KeyboardInterrupt:
        logging.info("Server shutdown requested by user")
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        print(f"Error starting server: {e}")
        return 1


if __name__ == "__main__":
    main()
