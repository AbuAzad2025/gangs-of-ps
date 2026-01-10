from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required
from flask_babel import _
from models import User
from models.social import Gang
from . import bp

@bp.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    user_results = []
    gang_results = []
    query = ""
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            user_results = User.query.filter(User.username.ilike(f'%{query}%')).limit(50).all()
            gang_results = Gang.query.filter(Gang.name.ilike(f'%{query}%')).limit(50).all()
            
            if not user_results and not gang_results:
                flash(_('لم يتم العثور على أي نتائج'), 'warning')
        else:
            flash(_('الرجاء إدخال اسم للبحث'), 'warning')
            
    return render_template('search.html', user_results=user_results, gang_results=gang_results, query=query)
