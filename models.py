from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'admin' or 'user'
    department = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    email_verified     = db.Column(db.Boolean, nullable=False, default=False)
    verification_token = db.Column(db.String(64), nullable=True)

    projects = db.relationship('Project', backref='creator', lazy=True,
                               foreign_keys='Project.created_by')
    attachments = db.relationship('Attachment', backref='uploader', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)

    def get_id(self):
        return str(self.id)


class Domain(db.Model):
    __tablename__ = 'domains'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), nullable=False, default='#6B7280')
    icon = db.Column(db.String(50), default='bi-folder')
    order_index = db.Column(db.Integer, default=0)

    projects = db.relationship('Project', backref='domain', lazy=True)


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    domain_id = db.Column(db.Integer, db.ForeignKey('domains.id'), nullable=False)
    business_sponsor = db.Column(db.String(200))
    business_owner = db.Column(db.String(200))
    it_owner = db.Column(db.String(200))
    vendor_partner = db.Column(db.String(200))
    status = db.Column(db.String(50), nullable=False, default='ideation')
    functional_requirements = db.Column(db.Text)
    estimated_start = db.Column(db.Date)
    estimated_end = db.Column(db.Date)
    revised_start = db.Column(db.Date)
    revised_end = db.Column(db.Date)
    cost = db.Column(db.Numeric(15, 2))
    technical_stack = db.Column(db.Text)
    technical_domain = db.Column(db.String(100))
    project_nature = db.Column(db.String(50))
    llm_used = db.Column(db.String(200))
    hosted_on = db.Column(db.String(50))
    hosted_on_other = db.Column(db.String(200))
    hosting_date = db.Column(db.Date)
    hosting_cost = db.Column(db.Numeric(15, 2))
    golive_date = db.Column(db.Date)
    termination_date = db.Column(db.Date)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attachments = db.relationship('Attachment', backref='project', lazy=True,
                                  cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='project', lazy=True,
                                 cascade='all, delete-orphan')
    process_mappings = db.relationship('ProjectProcess', backref='project', lazy=True,
                                       cascade='all, delete-orphan')


class Attachment(db.Model):
    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)          # UUID-based stored name
    original_filename = db.Column(db.String(255), nullable=False) # User-facing name
    file_size = db.Column(db.Integer)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    project_name = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # action: 'created', 'updated', 'status_change', 'attachment_added'
    action = db.Column(db.String(50), nullable=False)
    old_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50))
    notes = db.Column(db.Text)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)


class ETOMProcess(db.Model):
    __tablename__ = 'etom_processes'

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(20), unique=True, nullable=False, index=True)
    level       = db.Column(db.Integer, nullable=False)   # 1, 2, or 3
    name        = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    area        = db.Column(db.String(50), nullable=False)
    color       = db.Column(db.String(20), nullable=False, default='#6B7280')
    parent_code             = db.Column(db.String(20),  nullable=True, index=True)
    lightstorm_process_link = db.Column(db.String(500), nullable=True)
    version                 = db.Column(db.String(50),  nullable=True)
    comment                 = db.Column(db.Text,        nullable=True)

    mappings = db.relationship('ProjectProcess', backref='process', lazy='dynamic')


class ProjectProcess(db.Model):
    __tablename__ = 'project_processes'
    __table_args__ = (
        db.UniqueConstraint('project_id', 'process_id', name='uq_project_process'),
    )

    id                = db.Column(db.Integer, primary_key=True)
    project_id        = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    process_id        = db.Column(db.Integer, db.ForeignKey('etom_processes.id'), nullable=False, index=True)
    # valid: 'mapped', 'in_progress', 'compliant', 'gap', 'not_applicable'
    compliance_status = db.Column(db.String(30), nullable=False, default='mapped')
    notes             = db.Column(db.Text)
    mapped_by         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mapped_at         = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    auto_mapped       = db.Column(db.Boolean, nullable=False, default=False)

    mapper = db.relationship('User', backref='process_mappings', lazy=True)


class FieldChangeLog(db.Model):
    __tablename__ = 'field_change_log'

    id           = db.Column(db.Integer, primary_key=True)
    project_id   = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    project_name = db.Column(db.String(200), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action       = db.Column(db.String(20), nullable=False)   # 'created' | 'updated'
    field_label  = db.Column(db.String(100), nullable=False)
    old_value    = db.Column(db.String(200))
    new_value    = db.Column(db.String(200))
    changed_at   = db.Column(db.DateTime, default=datetime.utcnow)

    changer = db.relationship('User', backref='field_changes', lazy=True)
