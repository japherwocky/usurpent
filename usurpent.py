import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.web import HTTPError
from tornado.log import enable_pretty_logging
from markdown import markdown
from dotenv import load_dotenv

import os
import logging
import re
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
            (r"(?!\/static.*)(.*)/?", DocHandler),
        ]

        super().__init__(handlers, **settings)


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
