import os
import json
import smtplib
join = os.path.join
exists = os.path.exists

from logging import info, debug, error
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.web import HTTPError
from markdown import markdown

class App (tornado.web.Application):
    def __init__(self, debug=False):
        """
        Settings for our application
        """
        settings = dict(
            cookie_secret="changemeplz",  # ideally grab this out of an ENV variable or something
            login_url="/login",
            template_path="templates",
            static_path="static",
            xsrf_cookies=False,
            autoescape = None,
            debug = debug,  # restarts app server on changes to local files
        )

        """
        map URLs to Handlers, with regex patterns
        """

        from handlers.reddit import RedditProxy

        handlers = [
            (r"/", Home),
            (r"/reddit/(.*)/?", RedditProxy),
            (r"(?!\/static.*)(.*)/?", DocHandler),
        ]

        tornado.web.Application.__init__(self, handlers, **settings)


class Home(tornado.web.RequestHandler):
    def get(self):
        self.render('index.html', hello=True)

    def post(self):
        # render quickly
        self.render('index.html', hello=False)

        # parse and send off the email
        if 'msg' in self.request.arguments and 'from' in self.request.arguments:
            self.mailpeople(self.request.arguments['msg'][0], self.request.arguments['from'][0])

    def mailpeople(self, msg, contact):
        from keys import SMTP_USER, SMTP_PASS
        headers = 'From: j4ne@pearachute.com\nSubject: Incoming Message\n\n'
        email = """%s
        message:\n%s\n\n
        contact info:\n%s\n
        ip:\n%s\n----""" % (headers, msg, contact, self.request.remote_ip)

        try:
            m = smtplib.SMTP('email-smtp.us-east-1.amazonaws.com', 587)
            m.starttls()
            m.login(SMTP_USER, SMTP_PASS)

            recips = ['hello@pearachute.com']
            for recip in recips:
                m.sendmail('j4ne@pearachute.com', recip, email)
            m.quit()
        except:
            # make sure we don't lose the contact anyhow
            error(email)
            raise


class DocHandler(tornado.web.RequestHandler):
    """
        Main blog post handler.  Look in /docs/ for whatever
        the request is trying for, render it as markdown
    """
    def get(self, path):

        path = 'docs/' + path.replace('.', '').strip('/')
        if exists(path):
            #a folder
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
        #put tests in the tests folder
        import tests, unittest
        import sys
        sys.argv = ['pearachute.py', ]  # unittest messes with argv
        unittest.main('tests')
        return

    http_server = tornado.httpserver.HTTPServer( App(debug=options.debug), xheaders=True)
    http_server.listen(options.port)
    info('Serving on port %d' % options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
