# -*- coding: utf-8 -*-
"""
Gist embedding plugin for Pelican
=================================

This plugin allows you to embed `Gists`_ into your posts.

.. _Gists: https://gist.github.com/

"""
import logging
import hashlib
import os
import re


logger = logging.getLogger(__name__)
gist_regex = re.compile(r'(<p>\[gist:id\=([0-9a-fA-F]+)(,lexer\=([^\]]+))?\]</p>)')
gist_default_template = """<div class="gist">
    <script src='{{script_url}}'></script>
    <noscript>
        <pre><code>{{code}}</code></pre>
    </noscript>
</div>"""


def html_output(script_url, code):
    return ""


def gist_url(gist_id, filename=None):
    url = "https://raw.github.com/gist/{}".format(gist_id)
    if filename is not None:
        url += "/{}".format(filename)
    return url


def script_url(gist_id, filename=None):
    url = "https://gist.github.com/{}.js".format(gist_id)
    if filename is not None:
        url += "?file={}".format(filename)
    return url


def cache_filename(base, gist_id, filename=None):
    h = hashlib.md5()
    h.update(gist_id)
    if filename is not None:
        h.update(filename)
    return os.path.join(base, '{}.cache'.format(h.hexdigest()))


def get_cache(base, gist_id, filename=None):
    cache_file = cache_filename(base, gist_id, filename)
    if not os.path.exists(cache_file):
        return None
    with open(cache_file, 'r') as f:
        return f.read()


def set_cache(base, gist_id, body, filename=None):
    with open(cache_filename(base, gist_id, filename), 'w') as f:
        f.write(body)


def fetch_gist(gist_id, filename=None):
    """Fetch a gist and return the raw contents."""
    import requests

    url = gist_url(gist_id, filename)
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception('Got a bad status looking up gist.')
    body = response.content
    if not body:
        raise Exception('Unable to get the gist content.')

    return body


def setup_gist(pelican):
    """Setup the default settings."""

    pelican.settings.setdefault('GIST_CACHE_ENABLED', True)
    pelican.settings.setdefault('GIST_CACHE_LOCATION',
        '/tmp/gist-cache')

    pelican.settings.setdefault('GIST_TEMPLATE', gist_default_template)

    # Make sure the gist cache directory exists
    cache_base = pelican.settings.get('GIST_CACHE_LOCATION')
    if not os.path.exists(cache_base):
        os.makedirs(cache_base)


def replace_gist_tags(generator):
    """Replace gist tags in the article content."""
    from jinja2 import Template
    gist_template = generator.context.get('GIST_TEMPLATE')
    template = Template(gist_template)

    should_cache = generator.context.get('GIST_CACHE_ENABLED')
    cache_location = generator.context.get('GIST_CACHE_LOCATION')

    for article in generator.articles:
        for match in gist_regex.findall(article._content):
            gist_id = match[1]
            filename = None
            lexer = None
            if match[3]:
                lexer = match[3]
            #logger.info('[gist]: Found gist id {} and filename {}'.format(
            #    gist_id,
            #    filename
            #))

            if should_cache:
                body = get_cache(cache_location, gist_id, None) # filenmae avant

            # Fetch the gist
            if not body:
                logger.info('[gist]:   Gist did not exist in cache, fetching...')
                body = fetch_gist(gist_id, filename)

                if should_cache:
                    logger.info('[gist]:   Saving gist to cache...')
                    set_cache(cache_location, gist_id, body, filename)
            else:
                logger.info('[gist]:   Found gist in cache.')

            from pygments import highlight
            from pygments.formatters import HtmlFormatter
            from pygments.lexers import guess_lexer, get_lexer_by_name
            if lexer is None:
                lexer = guess_lexer(body)
            else:
                lexer = get_lexer_by_name(lexer)
            body = highlight(body.encode('utf-8'), lexer, HtmlFormatter())
            print body.encode('utf-8')


            # Create a context to render with
            context = generator.context.copy()
            context.update({
                'script_url': unicode(script_url(gist_id, filename), 'utf-8'),
                'gist_url': 'https://gist.github.com/{}'.format(gist_id),
                'code': body,
            })

            # Render the template
            replacement = template.render(context)

            article._content = article._content.replace(match[0], replacement)


def register():
    """Plugin registration."""
    from pelican import signals

    signals.initialized.connect(setup_gist)

    signals.article_generator_finalized.connect(replace_gist_tags)
