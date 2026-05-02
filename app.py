import os
import uuid
import random
import secrets
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

import csv
import io
from flask import (Flask, render_template, redirect, url_for, request,
                   flash, send_from_directory, abort, session, g, Response)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from models import db, User, Domain, Project, Attachment, AuditLog, ETOMProcess, ProjectProcess, FieldChangeLog
from config import Config

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
mail = Mail(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STATUSES = [
    ('ideation',               'Ideation',               '#6B7280', 'bi-lightbulb'),
    ('user_requirement',       'User Requirement',       '#3B82F6', 'bi-file-text'),
    ('incubation',             'Incubation',             '#F59E0B', 'bi-flask'),
    ('under_development',      'Under Development',      '#F97316', 'bi-code-slash'),
    ('live',                   'Live',                   '#10B981', 'bi-check-circle-fill'),
    ('continuous_enhancement', 'Continuous Enhancement', '#0EA5E9', 'bi-arrow-repeat'),
    ('phased_out',             'Phased Out',             '#EF4444', 'bi-archive'),
]

STATUS_MAP = {s[0]: {'label': s[1], 'color': s[2], 'icon': s[3]} for s in STATUSES}
STATUS_MATURITY = {s[0]: i + 1 for i, s in enumerate(STATUSES)}

COMPLIANCE_STATUSES = [
    ('mapped',         'Mapped',         '#6B7280', 'bi-link-45deg'),
    ('in_progress',    'In Progress',    '#F59E0B', 'bi-hourglass-split'),
    ('compliant',      'Compliant',      '#10B981', 'bi-check-circle-fill'),
    ('gap',            'Gap',            '#EF4444', 'bi-exclamation-triangle-fill'),
    ('not_applicable', 'Not Applicable', '#94A3B8', 'bi-dash-circle'),
]
COMPLIANCE_MAP = {s[0]: {'label': s[1], 'color': s[2], 'icon': s[3]} for s in COMPLIANCE_STATUSES}

TECHNICAL_DOMAINS = [
    'Business Process Automation',
    'Platforms',
    'MIS/Analytics',
    'AI Adoption',
]

PROJECT_NATURES = [
    'Strategic',
    'Tactical',
    'Operations',
]

PRIVILEGED_MAPPER_EMAIL = 'krishna.basudevan@lightstorm.net'

# Business domain → relevant eTOM L2 codes
DOMAIN_ETOM_MAP = {
    'Marketing':               ['1.1', '3.1'],
    'Sales':                   ['2.1', '1.1'],
    'Product':                 ['1.2', '1.1'],
    'Service Delivery':        ['2.2', '1.3'],
    'Network Planning':        ['1.4', '2.3'],
    'Network Operation':       ['2.3', '2.5'],
    'Customer Experience':     ['2.1', '2.2'],
    'Revenue Assurance':       ['2.6', '3.2'],
    'Supply Chain Management': ['1.5', '2.4'],
    'Financial Accounting':    ['3.3', '2.6'],
    'HR':                      ['3.4'],
    'Legal':                   ['3.2', '3.5'],
    'Regulatory':              ['3.2', '3.1'],
    'IT for IT':               ['3.7', '3.8', '2.3'],
    'Security':                ['3.2', '3.7'],
}

# Technical domain → additional eTOM L2 codes
TECH_DOMAIN_ETOM_MAP = {
    'Business Process Automation': ['3.8', '1.3'],
    'Platforms':                   ['1.4', '3.7'],
    'MIS/Analytics':               ['3.6', '3.7'],
    'AI Adoption':                 ['3.6', '3.7'],
}

# Nature of project → additional eTOM L2 codes
NATURE_ETOM_MAP = {
    'Strategic':  ['3.1', '3.9'],
    'Tactical':   ['3.9', '3.8'],
    'Operations': ['2.5', '3.10'],
}

# Canonical business domains — kept in sync with the domains table via init_db migration
CANONICAL_DOMAINS = [
    (1,  'Marketing',               'Marketing campaigns, brand, and digital presence',         '#EC4899', 'bi-megaphone'),
    (2,  'Sales',                   'Sales pipeline, CRM, and revenue generation',              '#2563EB', 'bi-graph-up-arrow'),
    (3,  'Product',                 'Product management, roadmap, and lifecycle',               '#6366F1', 'bi-box-seam'),
    (4,  'Service Delivery',        'Service fulfilment, provisioning, and operations',         '#7C3AED', 'bi-headset'),
    (5,  'Network Planning',        'Network design, capacity planning, and rollout',           '#0EA5E9', 'bi-diagram-3'),
    (6,  'Network Operation',       'Network monitoring, assurance, and incident management',   '#F97316', 'bi-activity'),
    (7,  'Customer Experience',     'Customer journey, satisfaction, and self-service',         '#10B981', 'bi-people-fill'),
    (8,  'Revenue Assurance',       'Billing accuracy, fraud prevention, and leakage control',  '#F59E0B', 'bi-currency-dollar'),
    (9,  'Supply Chain Management', 'Procurement, logistics, and vendor management',            '#8B5CF6', 'bi-truck'),
    (10, 'Financial Accounting',    'Finance, reporting, and cost management',                  '#059669', 'bi-calculator'),
    (11, 'HR',                      'Human resources, talent, and workforce management',        '#D97706', 'bi-person-badge'),
    (12, 'Legal',                   'Legal, contracts, and compliance management',              '#DC2626', 'bi-shield-check'),
    (13, 'Regulatory',              'Regulatory compliance, reporting, and governance',         '#6B7280', 'bi-clipboard-check'),
    (14, 'IT for IT',               'Internal IT infrastructure, tools, and support',           '#64748B', 'bi-gear-wide'),
    (15, 'Security',                'Cyber security, identity, and risk management',            '#1E293B', 'bi-lock-fill'),
]


def allowed_file(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in app.config['ALLOWED_EXTENSIONS']


# ---------------------------------------------------------------------------
# CSRF protection (simple session-based)
# ---------------------------------------------------------------------------
def generate_csrf():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(16)
    return session['_csrf_token']


app.jinja_env.globals['csrf_token'] = generate_csrf


@app.before_request
def csrf_protect():
    if request.method == 'POST':
        token = session.get('_csrf_token')
        form_token = request.form.get('_csrf_token')
        if not token or token != form_token:
            abort(403)


@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Server'] = 'ITPMO'
    return response


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Flask-Login
# ---------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Context processor
# ---------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    try:
        g_domains = Domain.query.order_by(Domain.order_index).all()
    except Exception:
        g_domains = []
    return {
        'STATUS_MAP': STATUS_MAP,
        'STATUSES': STATUSES,
        'STATUS_MATURITY': STATUS_MATURITY,
        'COMPLIANCE_MAP': COMPLIANCE_MAP,
        'COMPLIANCE_STATUSES': COMPLIANCE_STATUSES,
        'TECHNICAL_DOMAINS': TECHNICAL_DOMAINS,
        'PROJECT_NATURES': PROJECT_NATURES,
        'current_year': datetime.now().year,
        'g_domains': g_domains,
        'PRIVILEGED_MAPPER_EMAIL': PRIVILEGED_MAPPER_EMAIL,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _send_verification_email(user, token):
    verify_url = f"{app.config['APP_BASE_URL']}{url_for('verify_email', token=token)}"
    html_body = render_template('auth/verify_email.html',
                                username=user.username,
                                verify_url=verify_url)
    msg = Message(
        subject='Verify your ITPMO account',
        recipients=[user.email],
        html=html_body,
    )
    try:
        mail.send(msg)
    except Exception as exc:
        app.logger.error(f'Failed to send verification email to {user.email}: {exc}')


# Dropdown fields tracked in FieldChangeLog (field_attr, display label)
AUDITED_FIELDS = [
    ('domain_id',        'Business Domain'),
    ('technical_domain', 'Technical Domain'),
    ('project_nature',   'Nature of Project'),
    ('status',           'Project Status'),
    ('hosted_on',        'Hosted On'),
]


def _field_display(project, attr):
    if attr == 'domain_id':
        return project.domain.name if project.domain else None
    if attr == 'status':
        return STATUS_MAP.get(project.status, {}).get('label') if project.status else None
    return getattr(project, attr, None) or None


def _snapshot(project):
    return {attr: _field_display(project, attr) for attr, _ in AUDITED_FIELDS}


def _log_fields(project, old_snap, action, user_id):
    for attr, label in AUDITED_FIELDS:
        old = old_snap.get(attr)
        new = _field_display(project, attr)
        if action == 'created' and new:
            db.session.add(FieldChangeLog(
                project_id=project.id, project_name=project.name,
                user_id=user_id, action='created',
                field_label=label, old_value=None, new_value=new,
            ))
        elif action == 'updated' and old != new:
            db.session.add(FieldChangeLog(
                project_id=project.id, project_name=project.name,
                user_id=user_id, action='updated',
                field_label=label, old_value=old, new_value=new,
            ))


def parse_date(val):
    if not val:
        return None
    try:
        return datetime.strptime(val, '%Y-%m-%d').date()
    except ValueError:
        return None


def parse_cost(val):
    if not val:
        return None
    try:
        return float(str(val).replace(',', '').replace('$', '').strip())
    except ValueError:
        return None


def fmt_bytes(size):
    if size is None:
        return '—'
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f'{size:.0f} {unit}'
        size /= 1024
    return f'{size:.1f} TB'


app.jinja_env.filters['fmt_bytes'] = fmt_bytes


def auto_map_etom(project):
    """Auto-map project to eTOM L2 processes based on domain/tech domain/nature.
    Skips codes already manually mapped. Returns count of new mappings created."""
    codes = list(dict.fromkeys(
        DOMAIN_ETOM_MAP.get(project.domain.name, []) +
        TECH_DOMAIN_ETOM_MAP.get(project.technical_domain or '', []) +
        NATURE_ETOM_MAP.get(project.project_nature or '', [])
    ))
    if not codes:
        return 0

    already_mapped = {pp.process_id for pp in project.process_mappings}
    system_user = User.query.filter_by(email=PRIVILEGED_MAPPER_EMAIL).first()
    mapper_id = system_user.id if system_user else project.created_by

    added = 0
    for code in codes:
        proc = ETOMProcess.query.filter_by(code=code, level=2).first()
        if not proc or proc.id in already_mapped:
            continue
        db.session.add(ProjectProcess(
            project_id=project.id,
            process_id=proc.id,
            compliance_status='mapped',
            auto_mapped=True,
            mapped_by=mapper_id,
        ))
        already_mapped.add(proc.id)
        added += 1
    return added


# ===========================================================================
# HOME
# ===========================================================================
@app.route('/')
def index():
    domains = Domain.query.order_by(Domain.order_index).all()
    total_projects = Project.query.count()

    status_counts = {s[0]: Project.query.filter_by(status=s[0]).count() for s in STATUSES}

    domain_stats = []
    for domain in domains:
        all_p = Project.query.filter_by(domain_id=domain.id).all()
        domain_stats.append({
            'domain': domain,
            'total': len(all_p),
            'live': sum(1 for p in all_p if p.status == 'live'),
            'in_progress': sum(1 for p in all_p
                               if p.status in ('under_development', 'incubation')),
        })

    recent_activity = (AuditLog.query
                       .order_by(AuditLog.changed_at.desc())
                       .limit(8).all())

    # Pre-build chart data lists for Jinja2 (no list comprehension support)
    chart_labels = [s[1] for s in STATUSES]
    chart_counts = [status_counts[s[0]] for s in STATUSES]
    chart_colors = [s[2] for s in STATUSES]

    return render_template('index.html',
                           domains=domains,
                           total_projects=total_projects,
                           status_counts=status_counts,
                           domain_stats=domain_stats,
                           recent_activity=recent_activity,
                           chart_labels=chart_labels,
                           chart_counts=chart_counts,
                           chart_colors=chart_colors)


# ===========================================================================
# AUTH
# ===========================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'GET':
        session['captcha_a'] = random.randint(1, 9)
        session['captcha_b'] = random.randint(1, 9)

    if request.method == 'POST':
        # Validate CAPTCHA first
        try:
            captcha_answer = int(request.form.get('captcha', ''))
        except ValueError:
            captcha_answer = None
        expected = session.get('captcha_a', 0) + session.get('captcha_b', 0)
        # Regenerate so the numbers change on every failed attempt
        session['captcha_a'] = random.randint(1, 9)
        session['captcha_b'] = random.randint(1, 9)

        if captcha_answer != expected:
            flash('Incorrect answer to the security question. Please try again.', 'danger')
            return render_template('auth/login.html',
                                   captcha_a=session['captcha_a'],
                                   captcha_b=session['captcha_b'])

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()

        # Lockout check
        if user and user.locked_until and user.locked_until > datetime.utcnow():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
            flash(f'Account locked due to too many failed attempts. Try again in {remaining} minute(s).', 'danger')
            return render_template('auth/login.html',
                                   captcha_a=session['captcha_a'],
                                   captcha_b=session['captcha_b'])

        if user and user.is_active and check_password_hash(user.password_hash, password):
            if not user.email_verified:
                flash('Please verify your email address before signing in. '
                      'Check your inbox for the verification link.', 'warning')
                return render_template('auth/login.html',
                                       captcha_a=session['captcha_a'],
                                       captcha_b=session['captcha_b'])
            user.failed_logins = 0
            user.locked_until = None
            db.session.commit()
            login_user(user, remember=bool(request.form.get('remember')))
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(request.args.get('next') or url_for('index'))

        if user:
            user.failed_logins = (user.failed_logins or 0) + 1
            if user.failed_logins >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                user.failed_logins = 0
                flash('Too many failed attempts. Account locked for 15 minutes.', 'danger')
            else:
                flash(f'Invalid email or password. {5 - user.failed_logins} attempt(s) remaining.', 'danger')
            db.session.commit()
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html',
                           captcha_a=session.get('captcha_a', 1),
                           captcha_b=session.get('captcha_b', 1))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        department = request.form.get('department', '').strip()

        ALLOWED_DOMAINS = {'lightstorm.in', 'lightstorm.net', 'lightstorm.sg'}

        errors = []
        if not all([username, email, password]):
            errors.append('All required fields must be filled.')
        else:
            email_domain = email.split('@')[-1] if '@' in email else ''
            if email_domain not in ALLOWED_DOMAINS:
                errors.append('Registration is restricted to Lightstorm email addresses '
                               '(@lightstorm.in, @lightstorm.net, @lightstorm.sg).')
        if password != confirm:
            errors.append('Passwords do not match.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        elif not any(c.isupper() for c in password):
            errors.append('Password must contain at least one uppercase letter.')
        elif not any(c.isdigit() for c in password):
            errors.append('Password must contain at least one number.')
        elif not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            errors.append('Password must contain at least one special character (!@#$%^&* etc.).')
        if User.query.filter_by(email=email).first():
            errors.append('An account with that email address already exists.')
        if User.query.filter_by(username=username).first():
            errors.append('That username is not available. Please choose another.')

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            first_user = User.query.count() == 0
            token = secrets.token_urlsafe(32)
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role='admin' if first_user else 'user',
                department=department,
                email_verified=first_user,
                verification_token=None if first_user else token,
            )
            db.session.add(user)
            db.session.commit()

            if not first_user:
                _send_verification_email(user, token)
                flash('Account created! Please check your email and click the verification '
                      'link before signing in.', 'success')
            else:
                flash('Admin account created! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('auth/register.html')


@app.route('/verify-email/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash('Verification link is invalid or has already been used.', 'danger')
        return redirect(url_for('login'))
    user.email_verified = True
    user.verification_token = None
    db.session.commit()
    flash('Email verified successfully! You can now sign in.', 'success')
    return redirect(url_for('login'))


# ===========================================================================
# PROJECTS
# ===========================================================================
@app.route('/projects')
@login_required
def projects():
    domain_filter = request.args.get('domain', '')
    status_filter = request.args.get('status', '')
    search = request.args.get('q', '').strip()

    q = Project.query
    if domain_filter:
        q = q.filter_by(domain_id=domain_filter)
    if status_filter:
        q = q.filter_by(status=status_filter)
    if search:
        like = f'%{search}%'
        q = q.filter(
            Project.name.ilike(like) |
            Project.description.ilike(like) |
            Project.business_owner.ilike(like) |
            Project.it_owner.ilike(like)
        )

    projects_list = q.order_by(Project.updated_at.desc()).all()
    domains = Domain.query.order_by(Domain.order_index).all()
    return render_template('projects/list.html',
                           projects=projects_list,
                           domains=domains,
                           domain_filter=domain_filter,
                           status_filter=status_filter,
                           search=search)


@app.route('/projects/new', methods=['GET', 'POST'])
@login_required
def project_new():
    domains = Domain.query.order_by(Domain.order_index).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Project name is required.', 'danger')
            return render_template('projects/form.html', domains=domains, project=None)

        project = Project(
            name=name,
            description=request.form.get('description', '').strip(),
            domain_id=request.form.get('domain_id'),
            business_sponsor=request.form.get('business_sponsor', '').strip(),
            business_owner=request.form.get('business_owner', '').strip(),
            it_owner=request.form.get('it_owner', '').strip(),
            vendor_partner=request.form.get('vendor_partner', '').strip(),
            status=request.form.get('status', 'ideation'),
            functional_requirements=request.form.get('functional_requirements', '').strip(),
            estimated_start=parse_date(request.form.get('estimated_start')),
            estimated_end=parse_date(request.form.get('estimated_end')),
            revised_start=parse_date(request.form.get('revised_start')),
            revised_end=parse_date(request.form.get('revised_end')),
            cost=parse_cost(request.form.get('cost')),
            technical_stack=request.form.get('technical_stack', '').strip() or None,
            technical_domain=request.form.get('technical_domain', '').strip() or None,
            project_nature=request.form.get('project_nature', '').strip() or None,
            llm_used=request.form.get('llm_used', '').strip() or None,
            hosted_on=request.form.get('hosted_on', '').strip() or None,
            hosted_on_other=request.form.get('hosted_on_other', '').strip() or None,
            hosting_date=parse_date(request.form.get('hosting_date')),
            hosting_cost=parse_cost(request.form.get('hosting_cost')),
            golive_date=parse_date(request.form.get('golive_date')),
            termination_date=parse_date(request.form.get('termination_date')),
            created_by=current_user.id,
        )
        db.session.add(project)
        db.session.flush()

        log = AuditLog(
            project_id=project.id,
            project_name=project.name,
            user_id=current_user.id,
            action='created',
            new_status=project.status,
            notes=f'Project created by {current_user.username}',
        )
        db.session.add(log)
        auto_map_etom(project)
        _log_fields(project, {}, 'created', current_user.id)
        db.session.commit()

        flash(f'Project "{project.name}" created successfully!', 'success')
        return redirect(url_for('project_detail', id=project.id))

    return render_template('projects/form.html', domains=domains, project=None)


@app.route('/projects/<int:id>')
@login_required
def project_detail(id):
    project = Project.query.get_or_404(id)
    audit_logs = (AuditLog.query
                  .filter_by(project_id=id)
                  .order_by(AuditLog.changed_at.desc())
                  .all())

    # eTOM process mapping
    l2_list = ETOMProcess.query.filter_by(level=2).order_by(ETOMProcess.code).all()
    l3_list = ETOMProcess.query.filter_by(level=3).order_by(ETOMProcess.code).all()
    mapped_process_ids = {pp.process_id for pp in project.process_mappings}

    # Build L2 -> [L3] map for cascade select (passed as plain lists for Jinja)
    l3_by_l2 = {}
    for p in l3_list:
        l3_by_l2.setdefault(p.parent_code, []).append({'id': p.id, 'code': p.code, 'name': p.name})

    # Build JSON-safe structure for JS cascade
    import json
    cascade_data = {}
    for l2 in l2_list:
        cascade_data[l2.code] = {
            'id': l2.id,
            'name': f'{l2.code} {l2.name}',
            'children': l3_by_l2.get(l2.code, []),
        }
    cascade_json = json.dumps(cascade_data)

    field_audit = (FieldChangeLog.query
                   .filter_by(project_id=id)
                   .order_by(FieldChangeLog.changed_at.desc())
                   .all())

    return render_template('projects/detail.html',
                           project=project,
                           audit_logs=audit_logs,
                           field_audit=field_audit,
                           l2_list=l2_list,
                           cascade_json=cascade_json,
                           mapped_process_ids=mapped_process_ids)


@app.route('/projects/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def project_edit(id):
    project = Project.query.get_or_404(id)
    domains = Domain.query.order_by(Domain.order_index).all()

    if request.method == 'POST':
        old_status = project.status
        new_status = request.form.get('status', old_status)
        old_snap = _snapshot(project)

        project.name = request.form.get('name', '').strip() or project.name
        project.description = request.form.get('description', '').strip()
        project.domain_id = request.form.get('domain_id')
        project.business_sponsor = request.form.get('business_sponsor', '').strip()
        project.business_owner = request.form.get('business_owner', '').strip()
        project.it_owner = request.form.get('it_owner', '').strip()
        project.vendor_partner = request.form.get('vendor_partner', '').strip()
        project.functional_requirements = request.form.get('functional_requirements', '').strip()
        project.estimated_start = parse_date(request.form.get('estimated_start'))
        project.estimated_end = parse_date(request.form.get('estimated_end'))
        project.revised_start = parse_date(request.form.get('revised_start'))
        project.revised_end = parse_date(request.form.get('revised_end'))
        project.cost = parse_cost(request.form.get('cost'))
        project.technical_stack = request.form.get('technical_stack', '').strip() or None
        project.technical_domain = request.form.get('technical_domain', '').strip() or None
        project.project_nature = request.form.get('project_nature', '').strip() or None
        project.llm_used = request.form.get('llm_used', '').strip() or None
        project.hosted_on = request.form.get('hosted_on', '').strip() or None
        project.hosted_on_other = request.form.get('hosted_on_other', '').strip() or None
        project.hosting_date = parse_date(request.form.get('hosting_date'))
        project.hosting_cost = parse_cost(request.form.get('hosting_cost'))
        project.golive_date = parse_date(request.form.get('golive_date'))
        project.termination_date = parse_date(request.form.get('termination_date'))
        project.updated_at = datetime.utcnow()

        if new_status != old_status:
            project.status = new_status
            db.session.add(AuditLog(
                project_id=project.id,
                project_name=project.name,
                user_id=current_user.id,
                action='status_change',
                old_status=old_status,
                new_status=new_status,
                notes=request.form.get('status_notes', '').strip() or 'Status changed during edit',
            ))

        db.session.add(AuditLog(
            project_id=project.id,
            project_name=project.name,
            user_id=current_user.id,
            action='updated',
            notes=f'Project details updated by {current_user.username}',
        ))
        _log_fields(project, old_snap, 'updated', current_user.id)
        db.session.commit()

        flash(f'Project "{project.name}" updated successfully!', 'success')
        return redirect(url_for('project_detail', id=project.id))

    return render_template('projects/form.html', domains=domains, project=project)


@app.route('/projects/<int:id>/status', methods=['POST'])
@login_required
def project_change_status(id):
    project = Project.query.get_or_404(id)
    new_status = request.form.get('status')
    notes = request.form.get('notes', '').strip()

    valid = [s[0] for s in STATUSES]
    if new_status not in valid:
        flash('Invalid status value.', 'danger')
        return redirect(url_for('project_detail', id=id))

    old_status = project.status
    if new_status == old_status:
        flash('Status is already set to that value.', 'info')
        return redirect(url_for('project_detail', id=id))

    project.status = new_status
    project.updated_at = datetime.utcnow()

    db.session.add(AuditLog(
        project_id=project.id,
        project_name=project.name,
        user_id=current_user.id,
        action='status_change',
        old_status=old_status,
        new_status=new_status,
        notes=notes or None,
    ))
    db.session.commit()

    flash(
        f'Status changed: "{STATUS_MAP[old_status]["label"]}" → "{STATUS_MAP[new_status]["label"]}"',
        'success'
    )
    return redirect(url_for('project_detail', id=id))


@app.route('/projects/<int:id>/upload', methods=['POST'])
@login_required
def project_upload(id):
    project = Project.query.get_or_404(id)

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('project_detail', id=id))

    if not allowed_file(file.filename):
        flash('File type not allowed.', 'danger')
        return redirect(url_for('project_detail', id=id))

    original = secure_filename(file.filename)
    ext = original.rsplit('.', 1)[-1].lower()
    stored_name = f'{uuid.uuid4().hex}.{ext}'

    upload_dir = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, stored_name)
    file.save(filepath)

    att = Attachment(
        project_id=project.id,
        filename=stored_name,
        original_filename=original,
        file_size=os.path.getsize(filepath),
        uploaded_by=current_user.id,
    )
    db.session.add(att)
    db.session.add(AuditLog(
        project_id=project.id,
        project_name=project.name,
        user_id=current_user.id,
        action='attachment_added',
        notes=f'File "{original}" uploaded by {current_user.username}',
    ))
    db.session.commit()

    flash(f'"{original}" uploaded successfully.', 'success')
    return redirect(url_for('project_detail', id=id))


@app.route('/projects/<int:id>/download/<int:att_id>')
@login_required
def project_download(id, att_id):
    att = Attachment.query.filter_by(id=att_id, project_id=id).first_or_404()
    upload_dir = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    return send_from_directory(upload_dir, att.filename,
                               as_attachment=True,
                               download_name=att.original_filename)


@app.route('/projects/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def project_delete(id):
    project = Project.query.get_or_404(id)
    name = project.name
    upload_dir = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    for att in project.attachments:
        try:
            os.remove(os.path.join(upload_dir, att.filename))
        except OSError:
            pass
    db.session.delete(project)
    db.session.commit()
    flash(f'Project "{name}" has been deleted.', 'warning')
    return redirect(url_for('projects'))


# ===========================================================================
# PROCESS MAPPINGS (per project)
# ===========================================================================
@app.route('/projects/<int:id>/process-map', methods=['POST'])
@login_required
def project_process_map(id):
    project = Project.query.get_or_404(id)
    if current_user.email != PRIVILEGED_MAPPER_EMAIL:
        abort(403)
    process_id = request.form.get('process_id', type=int)
    compliance_status = request.form.get('compliance_status', 'mapped')
    notes = request.form.get('notes', '').strip()

    if not process_id:
        flash('Please select a process.', 'danger')
        return redirect(url_for('project_detail', id=id))

    proc = ETOMProcess.query.get_or_404(process_id)

    existing = ProjectProcess.query.filter_by(project_id=id, process_id=process_id).first()
    if existing:
        flash(f'Process "{proc.name}" is already mapped to this project.', 'warning')
        return redirect(url_for('project_detail', id=id))

    if compliance_status not in [s[0] for s in COMPLIANCE_STATUSES]:
        compliance_status = 'mapped'

    pp = ProjectProcess(
        project_id=id,
        process_id=process_id,
        compliance_status=compliance_status,
        notes=notes or None,
        mapped_by=current_user.id,
    )
    db.session.add(pp)
    db.session.commit()

    flash(f'Process "{proc.code} — {proc.name}" mapped successfully.', 'success')
    return redirect(url_for('project_detail', id=id))


@app.route('/projects/<int:id>/process-map/<int:pp_id>/remove', methods=['POST'])
@login_required
def project_process_remove(id, pp_id):
    pp = ProjectProcess.query.filter_by(id=pp_id, project_id=id).first_or_404()
    if current_user.email != PRIVILEGED_MAPPER_EMAIL:
        abort(403)
    proc_name = pp.process.name
    db.session.delete(pp)
    db.session.commit()
    flash(f'Process mapping for "{proc_name}" removed.', 'info')
    return redirect(url_for('project_detail', id=id))


@app.route('/projects/<int:id>/process-map/<int:pp_id>/status', methods=['POST'])
@login_required
def project_process_status(id, pp_id):
    pp = ProjectProcess.query.filter_by(id=pp_id, project_id=id).first_or_404()
    if current_user.email != PRIVILEGED_MAPPER_EMAIL:
        abort(403)
    new_status = request.form.get('compliance_status', 'mapped')
    if new_status not in [s[0] for s in COMPLIANCE_STATUSES]:
        new_status = 'mapped'
    pp.compliance_status = new_status
    notes_val = request.form.get('notes', '').strip()
    if notes_val:
        pp.notes = notes_val
    pp.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Compliance status updated to "{COMPLIANCE_MAP[new_status]["label"]}".', 'success')
    return redirect(url_for('project_detail', id=id))


@app.route('/projects/<int:id>/auto-map', methods=['POST'])
@login_required
def project_auto_map(id):
    project = Project.query.get_or_404(id)
    # Remove existing auto-mapped entries before re-mapping
    ProjectProcess.query.filter_by(project_id=id, auto_mapped=True).delete()
    db.session.flush()
    added = auto_map_etom(project)
    db.session.commit()
    flash(f'eTOM auto-mapping complete — {added} process(es) mapped.', 'success')
    return redirect(url_for('project_detail', id=id))


# ===========================================================================
# PROCESSES (eTOM browser)
# ===========================================================================
@app.route('/processes')
@login_required
def processes():
    l1_list = ETOMProcess.query.filter_by(level=1).order_by(ETOMProcess.code).all()
    l2_list = ETOMProcess.query.filter_by(level=2).order_by(ETOMProcess.code).all()
    l3_list = ETOMProcess.query.filter_by(level=3).order_by(ETOMProcess.code).all()

    l3_by_parent = {}
    for p in l3_list:
        l3_by_parent.setdefault(p.parent_code, []).append(p)

    l2_by_parent = {}
    for l2 in l2_list:
        l3s = l3_by_parent.get(l2.code, [])
        l2_obj = {
            'process': l2,
            'children': l3s,
            'mapped_count': sum(p.mappings.count() for p in l3s),
        }
        l2_by_parent.setdefault(l2.parent_code, []).append(l2_obj)

    tree = [{'process': l1, 'children': l2_by_parent.get(l1.code, [])} for l1 in l1_list]

    total_mapped = ProjectProcess.query.count()
    compliant_count = ProjectProcess.query.filter_by(compliance_status='compliant').count()
    gap_count = ProjectProcess.query.filter_by(compliance_status='gap').count()

    return render_template('processes/list.html',
                           tree=tree,
                           total_mapped=total_mapped,
                           compliant_count=compliant_count,
                           gap_count=gap_count)


@app.route('/processes/<code>/edit', methods=['POST'])
@login_required
def process_edit(code):
    proc = ETOMProcess.query.filter_by(code=code).first_or_404()
    proc.lightstorm_process_link = request.form.get('lightstorm_process_link', '').strip() or None
    proc.version = request.form.get('version', '').strip() or None
    proc.comment = request.form.get('comment', '').strip() or None
    db.session.commit()
    flash(f'Process "{proc.code} — {proc.name}" updated.', 'success')
    return redirect(url_for('process_detail', code=code))


@app.route('/processes/<code>')
@login_required
def process_detail(code):
    proc = ETOMProcess.query.filter_by(code=code).first_or_404()

    parent = None
    if proc.parent_code:
        parent = ETOMProcess.query.filter_by(code=proc.parent_code).first()

    grandparent = None
    if parent and parent.parent_code:
        grandparent = ETOMProcess.query.filter_by(code=parent.parent_code).first()

    children = ETOMProcess.query.filter_by(parent_code=code).order_by(ETOMProcess.code).all()

    if proc.level == 3:
        mappings = ProjectProcess.query.filter_by(process_id=proc.id).all()
    elif proc.level == 2:
        child_ids = [c.id for c in children]
        all_ids = [proc.id] + child_ids
        mappings = ProjectProcess.query.filter(ProjectProcess.process_id.in_(all_ids)).all()
    else:
        l2s = children
        l3_ids = []
        for l2 in l2s:
            l3s = ETOMProcess.query.filter_by(parent_code=l2.code).all()
            l3_ids.extend(c.id for c in l3s)
        all_ids = [proc.id] + [c.id for c in l2s] + l3_ids
        mappings = ProjectProcess.query.filter(ProjectProcess.process_id.in_(all_ids)).all()

    return render_template('processes/detail.html',
                           proc=proc,
                           parent=parent,
                           grandparent=grandparent,
                           children=children,
                           mappings=mappings)


# ===========================================================================
# DOMAIN VIEW
# ===========================================================================
@app.route('/domain/<int:id>')
@login_required
def domain_view(id):
    domain = Domain.query.get_or_404(id)
    projects_list = (Project.query
                     .filter_by(domain_id=id)
                     .order_by(Project.updated_at.desc())
                     .all())
    return render_template('domain.html', domain=domain, projects=projects_list)


# ===========================================================================
# ADMIN
# ===========================================================================
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_projects = Project.query.count()
    recent_logs = (AuditLog.query
                   .order_by(AuditLog.changed_at.desc())
                   .limit(20).all())

    domain_stats = [{
        'name': d.name,
        'color': d.color,
        'count': Project.query.filter_by(domain_id=d.id).count()
    } for d in Domain.query.all()]

    status_stats = [{
        'key': s[0],
        'label': s[1],
        'color': s[2],
        'icon': s[3],
        'count': Project.query.filter_by(status=s[0]).count()
    } for s in STATUSES]

    domain_names  = [d['name']  for d in domain_stats]
    domain_counts = [d['count'] for d in domain_stats]
    domain_colors = [d['color'] for d in domain_stats]

    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_projects=total_projects,
                           recent_logs=recent_logs,
                           domain_stats=domain_stats,
                           status_stats=status_stats,
                           domain_names=domain_names,
                           domain_counts=domain_counts,
                           domain_colors=domain_colors)


@app.route('/admin/audit-log')
@login_required
@admin_required
def admin_audit_log():
    page = request.args.get('page', 1, type=int)
    project_filter = request.args.get('project_id', '')
    action_filter = request.args.get('action', '')

    q = AuditLog.query
    if project_filter:
        q = q.filter_by(project_id=project_filter)
    if action_filter:
        q = q.filter_by(action=action_filter)

    logs = q.order_by(AuditLog.changed_at.desc()).paginate(
        page=page, per_page=50, error_out=False)
    all_projects = Project.query.order_by(Project.name).all()
    actions = ['created', 'updated', 'status_change', 'attachment_added']

    return render_template('admin/audit_log.html',
                           logs=logs,
                           all_projects=all_projects,
                           actions=actions,
                           project_filter=project_filter,
                           action_filter=action_filter)


@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/<int:id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def admin_toggle_admin(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('You cannot change your own role.', 'danger')
    else:
        user.role = 'user' if user.role == 'admin' else 'admin'
        db.session.commit()
        flash(f'{user.username} role set to {user.role}.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def admin_toggle_active(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
    else:
        user.is_active = not user.is_active
        db.session.commit()
        state = 'activated' if user.is_active else 'deactivated'
        flash(f'{user.username} has been {state}.', 'success')
    return redirect(url_for('admin_users'))


# ===========================================================================
# EXPORT
# ===========================================================================
@app.route('/admin/export/projects')
@login_required
@admin_required
def admin_export_projects():
    domain_filter = request.args.get('domain', '')
    status_filter = request.args.get('status', '')

    q = Project.query
    if domain_filter:
        q = q.filter_by(domain_id=domain_filter)
    if status_filter:
        q = q.filter_by(status=status_filter)
    projects = q.order_by(Project.domain_id, Project.name).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'ID', 'Project Name', 'Domain', 'Status', 'Maturity Level',
        'Description', 'Business Sponsor', 'Business Owner', 'IT Owner',
        'Vendor / Partner', 'Functional Requirements',
        'Est. Start Date', 'Est. End Date',
        'Revised Start Date', 'Revised End Date',
        'Cost (USD)', 'Attachments',
        'Created By', 'Created At', 'Last Updated',
    ])

    for p in projects:
        writer.writerow([
            p.id,
            p.name,
            p.domain.name,
            STATUS_MAP[p.status]['label'],
            STATUS_MATURITY[p.status],
            p.description or '',
            p.business_sponsor or '',
            p.business_owner or '',
            p.it_owner or '',
            p.vendor_partner or '',
            p.functional_requirements or '',
            p.estimated_start.isoformat() if p.estimated_start else '',
            p.estimated_end.isoformat() if p.estimated_end else '',
            p.revised_start.isoformat() if p.revised_start else '',
            p.revised_end.isoformat() if p.revised_end else '',
            float(p.cost) if p.cost else '',
            len(p.attachments),
            p.creator.username,
            p.created_at.strftime('%Y-%m-%d %H:%M'),
            p.updated_at.strftime('%Y-%m-%d %H:%M'),
        ])

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'lightstorm_projects_{timestamp}.csv'

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@app.route('/admin/export/compliance')
@login_required
@admin_required
def admin_export_compliance():
    mappings = (ProjectProcess.query
                .join(ETOMProcess)
                .join(Project)
                .order_by(ETOMProcess.code, Project.name)
                .all())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'eTOM Code', 'Process Name', 'Level', 'Area',
        'Project ID', 'Project Name', 'Domain', 'Project Status',
        'Compliance Status', 'Notes', 'Mapped By', 'Mapped At', 'Updated At',
    ])
    for pp in mappings:
        writer.writerow([
            pp.process.code,
            pp.process.name,
            pp.process.level,
            pp.process.area,
            pp.project.id,
            pp.project.name,
            pp.project.domain.name,
            STATUS_MAP[pp.project.status]['label'],
            COMPLIANCE_MAP[pp.compliance_status]['label'],
            pp.notes or '',
            pp.mapper.username,
            pp.mapped_at.strftime('%Y-%m-%d %H:%M'),
            pp.updated_at.strftime('%Y-%m-%d %H:%M'),
        ])

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'lightstorm_compliance_{timestamp}.csv'
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# ===========================================================================
# HEALTH CHECK  (used by Docker HEALTHCHECK and load-balancers)
# ===========================================================================
@app.route('/health')
def health():
    return Response('ok', status=200, mimetype='text/plain')


# ===========================================================================
# ERROR HANDLERS
# ===========================================================================
@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


# ===========================================================================
# DB INIT + SEED
# ===========================================================================
def init_db():
    with app.app_context():
        db.create_all()

        # Migrate: add new columns to etom_processes if they don't exist yet.
        # Must run before any ORM query on ETOMProcess (SQLAlchemy includes all
        # mapped columns in every SELECT, so missing columns cause errors).
        import sqlalchemy as _sa
        _inspector = _sa.inspect(db.engine)
        if _inspector.has_table('etom_processes'):
            _cols = [c['name'] for c in _inspector.get_columns('etom_processes')]
            with db.engine.connect() as _conn:
                for _col, _ddl in [
                    ('lightstorm_process_link', 'VARCHAR(500)'),
                    ('version',                'VARCHAR(50)'),
                    ('comment',                'TEXT'),
                ]:
                    if _col not in _cols:
                        _conn.execute(_sa.text(f'ALTER TABLE etom_processes ADD COLUMN {_col} {_ddl}'))
                _conn.commit()

        if _inspector.has_table('projects'):
            _proj_cols = [c['name'] for c in _inspector.get_columns('projects')]
            with db.engine.connect() as _conn:
                for _col, _ddl in [
                    ('technical_stack',  'TEXT'),
                    ('technical_domain', 'VARCHAR(100)'),
                    ('project_nature',   'VARCHAR(50)'),
                    ('llm_used',         'VARCHAR(200)'),
                    ('hosted_on',        'VARCHAR(50)'),
                    ('hosted_on_other',  'VARCHAR(200)'),
                    ('hosting_date',     'DATE'),
                    ('hosting_cost',     'NUMERIC(15,2)'),
                    ('golive_date',      'DATE'),
                    ('termination_date', 'DATE'),
                ]:
                    if _col not in _proj_cols:
                        _conn.execute(_sa.text(f'ALTER TABLE projects ADD COLUMN {_col} {_ddl}'))
                _conn.commit()

        if _inspector.has_table('project_processes'):
            _pp_cols = [c['name'] for c in _inspector.get_columns('project_processes')]
            with db.engine.connect() as _conn:
                if 'auto_mapped' not in _pp_cols:
                    _conn.execute(_sa.text('ALTER TABLE project_processes ADD COLUMN auto_mapped INTEGER NOT NULL DEFAULT 0'))
                _conn.commit()

        if _inspector.has_table('users'):
            _user_cols = [c['name'] for c in _inspector.get_columns('users')]
            with db.engine.connect() as _conn:
                if 'email_verified' not in _user_cols:
                    _conn.execute(_sa.text('ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0'))
                    # Grandfather in existing accounts so they are not locked out
                    _conn.execute(_sa.text('UPDATE users SET email_verified = 1'))
                if 'verification_token' not in _user_cols:
                    _conn.execute(_sa.text('ALTER TABLE users ADD COLUMN verification_token VARCHAR(64)'))
                if 'failed_logins' not in _user_cols:
                    _conn.execute(_sa.text('ALTER TABLE users ADD COLUMN failed_logins INTEGER NOT NULL DEFAULT 0'))
                if 'locked_until' not in _user_cols:
                    _conn.execute(_sa.text('ALTER TABLE users ADD COLUMN locked_until TIMESTAMP'))
                _conn.commit()

        # field_change_log is created by db.create_all() above (new table).
        # No ALTER TABLE needed — it didn't exist before.

        # Sync domains table to CANONICAL_DOMAINS (upsert by order_index)
        existing_by_idx = {d.order_index: d for d in Domain.query.all()}
        for order_index, name, description, color, icon in CANONICAL_DOMAINS:
            if order_index in existing_by_idx:
                d = existing_by_idx[order_index]
                d.name = name
                d.description = description
                d.color = color
                d.icon = icon
            else:
                db.session.add(Domain(
                    name=name, description=description,
                    color=color, icon=icon, order_index=order_index,
                ))
        db.session.commit()
        print('[init] Domains synced.')

        if ETOMProcess.query.count() == 0:
            from etom_data import ETOM_PROCESSES
            for row in ETOM_PROCESSES:
                db.session.add(ETOMProcess(
                    code=row['code'],
                    level=row['level'],
                    name=row['name'],
                    description=row.get('description', ''),
                    area=row['area'],
                    color=row['color'],
                    parent_code=row.get('parent_code'),
                ))
            db.session.commit()
            print(f'[init] {len(ETOM_PROCESSES)} eTOM processes seeded.')

        # Ensure the designated admin account exists and has admin role
        _admin_email = 'krishna.basudevan@lightstorm.net'
        _admin = User.query.filter_by(email=_admin_email).first()
        if not _admin:
            db.session.add(User(
                username='krishna.basudevan',
                email=_admin_email,
                password_hash=generate_password_hash('Admin@2026!'),
                role='admin',
                department='IT',
                is_active=True,
                email_verified=True,
            ))
            db.session.commit()
            print(f'[init] Admin user {_admin_email} created.')
        elif _admin.role != 'admin':
            _admin.role = 'admin'
            _admin.email_verified = True
            db.session.commit()
            print(f'[init] Admin role restored for {_admin_email}.')


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
