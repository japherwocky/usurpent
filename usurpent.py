import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado import websocket
from tornado.web import HTTPError
from tornado.log import enable_pretty_logging
from markdown import markdown
from dotenv import load_dotenv

import config
import protocol

import os
import logging
import re
import math
import random
import json
join = os.path.join
exists = os.path.exists

# Load environment variables from .env file
load_dotenv()


class BaseHandler(tornado.web.RequestHandler):
    """Base handler with security headers"""
    
    def set_default_headers(self):
        """Set security headers for all responses"""
        self.set_header("X-Content-Type-Options", "nosniff")
        self.set_header("X-Frame-Options", "DENY")
        self.set_header("X-XSS-Protection", "1; mode=block")
        self.set_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.set_header("Content-Security-Policy", 
                       "default-src 'self'; "
                       "script-src 'self' 'unsafe-inline'; "
                       "style-src 'self' 'unsafe-inline'; "
                       "img-src 'self' data:; "
                       "font-src 'self'; "
                       "connect-src 'self'")
        
        # HSTS (only in production with HTTPS)
        if not self.application.settings.get('debug'):
            self.set_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


def _wrap_angle(angle):
    """Normalize an angle to (-pi, pi]."""
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle <= -math.pi:
        angle += 2 * math.pi
    return angle


class Player:
    """One snake on the map. Server-authoritative state only."""

    def __init__(self, player_id, handler, x, y):
        self.id = player_id
        self.handler = handler
        self.x = x
        self.y = y
        self.heading = random.uniform(-math.pi, math.pi)
        self.target = (x, y)
        self.alive = True
        self.score = 0
        self.length = config.INITIAL_TAIL_LENGTH
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
        desired = math.atan2(ty - self.y, tx - self.x)
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
        }


class World:
    """Authoritative game state, ticked at a fixed rate."""

    def __init__(self):
        self.players = {}  # player_id -> Player
        self._next_id = 0
        self.tick_count = 0
        self._callback = None

    def start(self):
        """Begin the simulation loop on the current IOLoop."""
        interval_ms = 1000.0 / config.TICK_HZ
        self._callback = tornado.ioloop.PeriodicCallback(self.tick, interval_ms)
        self._callback.start()

    def stop(self):
        if self._callback is not None:
            self._callback.stop()

    def spawn_player(self, handler):
        self._next_id += 1
        player_id = str(self._next_id)
        margin = config.INITIAL_TAIL_LENGTH * config.TAIL_SEGMENT_SPACING
        x = random.uniform(margin, config.MAP_WIDTH - margin)
        y = random.uniform(margin, config.MAP_HEIGHT - margin)
        player = Player(player_id, handler, x, y)
        self.players[player_id] = player
        handler.player_id = player_id
        logging.info(f"Player {player_id} spawned (total: {len(self.players)})")
        handler.write_message(self._welcome(player_id))
        self._broadcast_snapshot()
        return player_id

    def remove_player(self, player_id):
        self.players.pop(player_id, None)
        logging.info(f"Player {player_id} removed (total: {len(self.players)})")
        self._broadcast_snapshot()

    def tick(self):
        dt = 1.0 / config.TICK_HZ
        self.tick_count += 1
        for player in self.players.values():
            player.step(dt)
        self._broadcast_snapshot()

    def _snapshot(self):
        return {
            protocol.FIELD_TYPE: protocol.TYPE_SNAPSHOT,
            protocol.FIELD_TICK: self.tick_count,
            protocol.FIELD_PLAYERS: [p.to_dict() for p in self.players.values()],
        }

    def _welcome(self, self_id):
        return {
            protocol.FIELD_TYPE: protocol.TYPE_WELCOME,
            protocol.FIELD_SELF_ID: self_id,
            protocol.FIELD_MAP_WIDTH: config.MAP_WIDTH,
            protocol.FIELD_MAP_HEIGHT: config.MAP_HEIGHT,
            protocol.FIELD_PLAYERS: [p.to_dict() for p in self.players.values()],
        }

    def _broadcast_snapshot(self):
        snapshot = self._snapshot()
        for player in self.players.values():
            if player.handler is not None:
                player.handler.write_message(snapshot)


class GameWebSocketHandler(BaseHandler, websocket.WebSocketHandler):
    """Real-time game connection.

    Step 3: spawns a Player on connect, accepts mouse-target input, and
    receives 20 Hz snapshots from the World. Collisions/food land later.
    """

    def open(self):
        self.player_id = None
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


class App (tornado.web.Application):
    def __init__(self, debug=False):
        """
        Settings for our application
        """
        # Get cookie secret from environment or generate a warning
        cookie_secret = os.getenv('COOKIE_SECRET')
        if not cookie_secret or cookie_secret == 'changemeplz':
            logging.warning("Using default cookie secret! Set COOKIE_SECRET in .env for production.")
            cookie_secret = "changemeplz"  # fallback for development
        
        settings = dict(
            cookie_secret=cookie_secret,
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=debug,
            autoescape=None,  # disable autoescaping for our HTML docs
        )

        handlers = [
            (r"/?$", Home),
            (r"/ws", GameWebSocketHandler),
            (r"(?!\/static.*)(.*)/?", DocHandler),
        ]

        super().__init__(handlers, **settings)
        self.world = World()
        self.world.start()


class Home(BaseHandler):
    async def get(self):
        try:
            logging.info("Serving home page")
            self.render('index.html', hello=True)
        except Exception as e:
            logging.error(f"Error serving home page: {e}")
            raise HTTPError(500, "Internal server error")


class DocHandler(BaseHandler):
    """
        Main blog post handler.  Look in /docs/ for whatever
        the request is trying for, render it as markdown
    """
    async def get(self, path):
        try:
            logging.info(f"Processing documentation request for: {path}")
            
            # Input validation and sanitization
            if not path or not isinstance(path, str):
                logging.warning(f"Invalid path parameter: {path}")
                raise HTTPError(400, "Invalid path parameter")
            
            # Remove dangerous characters and patterns
            sanitized_path = path.replace('..', '').replace('\\', '/').strip('/')
            
            # Validate path contains only safe characters
            if not re.match(r'^[a-zA-Z0-9_\-/]+$', sanitized_path):
                logging.warning(f"Path contains invalid characters: {sanitized_path}")
                raise HTTPError(400, "Invalid path characters")
            
            # Ensure path stays within docs directory
            base_path = 'docs'
            full_path = os.path.normpath(os.path.join(base_path, sanitized_path))
            
            # Security check: ensure the resolved path is still within docs directory
            if not full_path.startswith(os.path.abspath(base_path)):
                logging.warning(f"Path traversal attempt detected: {path}")
                raise HTTPError(403, "Access denied")
            
            txt = None
            if exists(full_path) and os.path.isdir(full_path):
                # a folder
                lastname = os.path.split(full_path)[-1]
                file_path = os.path.join(full_path, f'{lastname}.txt')
                
                # Additional security check for file path
                if not file_path.startswith(os.path.abspath(base_path)):
                    logging.warning(f"File path traversal attempt: {file_path}")
                    raise HTTPError(403, "Access denied")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        txt = f.read()
                except IOError as e:
                    logging.error(f"Failed to read folder documentation {file_path}: {e}")
                    raise HTTPError(500, "Failed to read documentation")

            elif exists(full_path + '.txt'):
                file_path = full_path + '.txt'
                
                # Security check for file path
                if not file_path.startswith(os.path.abspath(base_path)):
                    logging.warning(f"File path traversal attempt: {file_path}")
                    raise HTTPError(403, "Access denied")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        txt = f.read()
                except IOError as e:
                    logging.error(f"Failed to read documentation {file_path}: {e}")
                    raise HTTPError(500, "Failed to read documentation")
            else:
                logging.warning(f"Documentation not found: {full_path}")
                raise HTTPError(404, "Documentation not found")

            if not txt:
                logging.warning(f"Empty documentation file: {full_path}")
                raise HTTPError(404, "Documentation not found")

            logging.debug(f"Successfully loaded documentation, length: {len(txt)}")
            doc = markdown(txt)
            self.render('legacy.html', doc=doc)
            
        except HTTPError:
            # Re-raise HTTP errors as-is
            raise
        except Exception as e:
            logging.error(f"Unexpected error processing documentation {path}: {e}")
            raise HTTPError(500, "Internal server error")


def main():
    from tornado.options import define, options
    define("port", default=int(os.getenv('PORT', 8001)), help="run on the given port", type=int)
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
