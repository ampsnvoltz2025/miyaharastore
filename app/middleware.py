from flask import request, redirect, url_for

def init_app(app):
    @app.before_request
    def redirect_to_https():
        # Skip for local development without HTTPS
        if request.url.startswith('http://') and not request.is_secure:
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)
