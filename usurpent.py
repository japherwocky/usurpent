import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.web import HTTPError
from markdown import markdown

import os
import logging
join = os.path.join
exists = os.path.exists


class App (tornado.web.Application):
    def __init__(self, debug=False):
        """
        Settings for our application
        """
        settings = dict(
            cookie_secret="changemeplz",  # ideally grab this out of an ENV var
            login_url="/login",
            template_path="templates",
            static_path="static",
            xsrf_cookies=False,
            autoescape=None,
            debug=debug,  # restarts app server on changes to local files
        )

        """
        map URLs to Handlers, with regex patterns
        """

        handlers = [
            (r"/?$", Home),
            (r"(?!\/static.*)(.*)/?", DocHandler),
        ]

        tornado.web.Application.__init__(self, handlers, **settings)


class Home(tornado.web.RequestHandler):
    def get(self):
        self.render('index.html', hello=True)


class DocHandler(tornado.web.RequestHandler):
    """
        Main blog post handler.  Look in /docs/ for whatever
        the request is trying for, render it as markdown
    """
    def get(self, path):

        path = 'docs/' + path.replace('.', '').strip('/')
        if exists(path):
            # a folder
            lastname = os.path.split(path)[-1]
            txt = open('%s/%s.txt' % (path, lastname)).read()

        elif exists(path + '.txt'):
            txt = open(path+'.txt').read()

        else:
            # does not exist!
            raise HTTPError(404)

        doc = markdown(unicode(txt, 'utf-8'))
        self.render('legacy.html', doc=doc)


def main():
    from tornado.options import define, options
    define("port", default=8001, help="run on the given port", type=int)
    define("debug", default=False, help="run server in debug mode", type=bool)
    define("runtests", default=False, help="run tests", type=bool)

    tornado.options.parse_command_line()

    if options.runtests:
        # put tests in the tests folder
        import tests, unittest
        import sys
        sys.argv = ['pearachute.py', ]  # unittest messes with argv
        unittest.main('tests')
        return

    http_server = tornado.httpserver.HTTPServer(App(debug=options.debug), xheaders=True)
    http_server.listen(options.port)
    logging.info('Serving on port %d' % options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
