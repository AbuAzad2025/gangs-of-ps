from flask import request, current_app, url_for, g
from flask_babel import gettext as _
import json

class SEOManager:
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.context_processor(self.context_processor)

    def context_processor(self):
        return dict(seo=self)

    @property
    def title(self):
        return g.get('seo_title', _('عصابات فلسطين'))

    @title.setter
    def title(self, value):
        g.seo_title = value

    @property
    def description(self):
        default_description = _('عصابات فلسطين - اللعبة العربية الاستراتيجية الأولى. عش تجربة حياة الجريمة المنظمة، ابنِ إمبراطوريتك في القدس وغزة، وتحدى الاحتلال. نافس آلاف اللاعبين في حروب العصابات. سجل الآن مجاناً!')
        return g.get('seo_description', default_description)

    @description.setter
    def description(self, value):
        g.seo_description = value

    @property
    def keywords(self):
        # Enhanced keywords for better visibility on Google and YouTube
        default_keywords = _("عصابات فلسطين, Gangs of Palestine, لعبة مافيا, حرب العصابات, العاب استراتيجية, فلسطين, القدس, غزة, العاب عربية, Mafia Game, Online RPG, Browser Game, العاب اونلاين, العاب اكشن, لعبة حرب, العاب متصفح, العاب مجانية, Free Games, Strategy Games, Multiplayer, PvP, Clan Wars, Palestine Game, Gaza, Jerusalem, Azad Company, العاب يوتيوب, العاب مشهورة")
        return g.get('seo_keywords', default_keywords)

    @keywords.setter
    def keywords(self, value):
        g.seo_keywords = value

    @property
    def image(self):
        default_image = url_for('static', filename='images/azad_logo_white_on_dark.png', _external=True)
        return g.get('seo_image', default_image)

    @image.setter
    def image(self, value):
        if not value.startswith('http'):
            # Assume it's a static file path if not a full URL
            # But usually we pass full URL or handle it here. 
            # For safety, let's assume the caller passes a full URL or we use url_for if needed.
            # Here we just store what is passed.
            pass
        g.seo_image = value

    @property
    def url(self):
        return request.url

    @property
    def type(self):
        return g.get('seo_type', 'website')

    @type.setter
    def type(self, value):
        g.seo_type = value

    @property
    def schema(self):
        return g.get('seo_schema', None)

    @schema.setter
    def schema(self, value):
        """
        Set structured data (JSON-LD dictionary).
        """
        g.seo_schema = value

    def set(self, title=None, description=None, keywords=None, image=None, type=None, schema=None):
        """
        Helper to set multiple properties at once.
        """
        if title:
            self.title = title
        if description:
            self.description = description
        if keywords:
            self.keywords = keywords
        if image:
            self.image = image
        if type:
            self.type = type
        if schema:
            self.schema = schema

    @property
    def breadcrumbs(self):
        return g.get('seo_breadcrumbs', [])

    def add_breadcrumb(self, name, url):
        breadcrumbs = self.breadcrumbs
        # Check if already exists to avoid duplicates if called multiple times
        if not any(b['item'] == url for b in breadcrumbs):
            breadcrumbs.append({'name': name, 'item': url})
        g.seo_breadcrumbs = breadcrumbs

    def render_breadcrumbs_schema(self):
        breadcrumbs = self.breadcrumbs
        if not breadcrumbs:
            return ""
        
        items = []
        for i, crumb in enumerate(breadcrumbs):
            # Fix for Google Search Console: Use simple ID reference
            items.append({
                "@type": "ListItem",
                "position": i + 1,
                "name": crumb['name'],
                "item": crumb['item']
            })
            
        schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": items
        }
        
        return f'<script type="application/ld+json">{json.dumps(schema)}</script>'

    def render_canonical(self):
        # Remove query parameters for canonical, unless pagination?
        # For now, let's keep it simple: strict canonical to the route URL without query params
        # or maybe we want query params for some things.
        # Let's use request.base_url which includes path but not query string.
        return f'<link rel="canonical" href="{request.base_url}">'

    def render_hreflang(self):
        # Generate alternate links for supported languages
        # Assuming we have a route that handles language or we use query params/session.
        # If our URL structure doesn't change with language (session based), hreflang might be tricky.
        # But if we want to be strict, we should probably have /ar/ and /en/ prefixes.
        # Since the current app seems to use session for language (based on core.py set_language),
        # strictly speaking, we don't have unique URLs for languages. 
        # So hreflang might not be applicable or we should point to the same URL with x-default.
        # However, for SEO, it's better to have distinct URLs. 
        # Since we can't easily change the routing structure right now, 
        # let's just output the current URL as x-default.
        return f'<link rel="alternate" hreflang="x-default" href="{request.base_url}">'
