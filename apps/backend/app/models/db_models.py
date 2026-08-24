import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base

def utc_now():
    return datetime.now(timezone.utc)

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    archived = Column(Boolean, default=False, nullable=False)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    model = Column(String(100), nullable=True)
    metadata_json = Column(Text, nullable=True)

    conversation = relationship("Conversation", back_populates="messages")

Index("idx_messages_conversation_id", Message.conversation_id)


class Note(Base):
    __tablename__ = "notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_path = Column(String(512), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    source = Column(String(100), default="user")
    tags_json = Column(Text, nullable=True)
    classification = Column(String(20), default="PRIVATE", nullable=False)

Index("idx_notes_file_path", Note.file_path)


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_type = Column(String(50), nullable=False)
    source_id = Column(String(36), nullable=True)
    content = Column(Text, nullable=False)
    memory_tier = Column(String(20), nullable=False)  # 'CORE', 'RECALL', 'ARCHIVAL'
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    metadata_json = Column(Text, nullable=True)
    classification = Column(String(20), default="PRIVATE", nullable=False)

Index("idx_memory_tier", MemoryItem.memory_tier)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    question = Column(Text, nullable=False)
    status = Column(String(20), default="OPEN", nullable=False)
    final_recommendation = Column(Text, nullable=True)
    reasoning_summary = Column(Text, nullable=True)
    agreements_json = Column(Text, nullable=True)
    conflicts_json = Column(Text, nullable=True)
    critical_risks_json = Column(Text, nullable=True)
    next_actions_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    executive_inputs = relationship("DecisionExecutiveInput", back_populates="decision", cascade="all, delete-orphan")


class DecisionExecutiveInput(Base):
    __tablename__ = "decision_executive_inputs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    decision_id = Column(String(36), ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(10), nullable=False)
    summary = Column(Text, nullable=False)
    key_findings_json = Column(Text, nullable=True)
    assumptions_json = Column(Text, nullable=True)
    risks_json = Column(Text, nullable=True)
    recommendations_json = Column(Text, nullable=True)
    confidence = Column(String(10), default="MEDIUM", nullable=False)
    missing_info_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    decision = relationship("Decision", back_populates="executive_inputs")

Index("idx_decision_inputs_decision_id", DecisionExecutiveInput.decision_id)


# --- Phase 4 Developer Intelligence Tables ---

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    root_path = Column(String(1024), unique=True, nullable=False)
    project_type = Column(String(100), nullable=True)
    language = Column(String(100), nullable=True)
    framework = Column(String(100), nullable=True)
    package_manager = Column(String(100), nullable=True)
    is_git = Column(Boolean, default=False, nullable=False)
    git_branch = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    proposals = relationship("CodeChangeProposal", back_populates="workspace", cascade="all, delete-orphan")
    agent_tasks = relationship("AgentTask", back_populates="workspace")


class CodeChangeProposal(Base):
    __tablename__ = "code_change_proposals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    risk_level = Column(String(20), default="LOW", nullable=False)
    diff_content = Column(Text, nullable=False)
    files_json = Column(Text, nullable=False)
    status = Column(String(20), default="PROPOSED", nullable=False)
    backup_path = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="proposals")

Index("idx_proposals_workspace_id", CodeChangeProposal.workspace_id)


# --- Phase 5 Agent Runtime Tables ---

class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    user_goal = Column(Text, nullable=False)
    status = Column(String(30), default="CREATED", nullable=False)  # CREATED, PLANNING, AWAITING_APPROVAL, RUNNING, PAUSED, VALIDATING, COMPLETED, FAILED, CANCELLED, EXPIRED
    risk_level = Column(String(20), default="LOW", nullable=False)
    current_step = Column(Integer, default=0, nullable=False)
    max_steps = Column(Integer, default=20, nullable=False)
    steps_completed = Column(Integer, default=0, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    requires_approval = Column(Boolean, default=False, nullable=False)
    plan_id = Column(String(36), nullable=True)
    result = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="agent_tasks")
    steps = relationship("AgentStep", back_populates="task", cascade="all, delete-orphan", order_by="AgentStep.sequence")

Index("idx_agent_tasks_status", AgentTask.status)


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False)
    sequence = Column(Integer, nullable=False)
    objective = Column(Text, nullable=False)
    action_type = Column(String(50), nullable=False)  # e.g. "TOOL_CALL", "ANALYSIS", "VALIDATION"
    tool_name = Column(String(100), nullable=False)
    arguments_json = Column(Text, nullable=False, default="{}")
    status = Column(String(30), default="PENDING", nullable=False)  # PENDING, RUNNING, AWAITING_APPROVAL, COMPLETED, FAILED, SKIPPED
    risk_level = Column(String(20), default="LOW", nullable=False)
    approval_required = Column(Boolean, default=False, nullable=False)
    approval_id = Column(String(36), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    task = relationship("AgentTask", back_populates="steps")

Index("idx_agent_steps_task_id", AgentStep.task_id)


class WebSite(Base):
    """Aggregated site metadata (used for autocomplete, frecency, visit count, title & favicons)"""
    __tablename__ = "web_sites"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    url = Column(String(1024), nullable=False)
    title = Column(String(512), nullable=False)
    profile_id = Column(String(64), default="default", nullable=False)
    visit_count = Column(Integer, default=1, nullable=False)
    last_visited_at = Column(DateTime, default=utc_now, nullable=False)

    visits = relationship("WebVisit", back_populates="site", cascade="all, delete-orphan")

Index("idx_web_sites_url_profile", WebSite.url, WebSite.profile_id)
Index("idx_web_sites_last_visited", WebSite.last_visited_at.desc())


class WebVisit(Base):
    """Chronological visit events (every single page visit in user timeline)"""
    __tablename__ = "web_visits"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    site_id = Column(String(36), ForeignKey("web_sites.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(1024), nullable=False)
    title = Column(String(512), nullable=False)
    profile_id = Column(String(64), default="default", nullable=False)
    visited_at = Column(DateTime, default=utc_now, nullable=False)

    site = relationship("WebSite", back_populates="visits")

Index("idx_web_visits_visited_at", WebVisit.visited_at.desc())
Index("idx_web_visits_profile", WebVisit.profile_id)


class WebBookmark(Base):
    __tablename__ = "web_bookmarks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    url = Column(String(1024), nullable=False)
    title = Column(String(512), nullable=False)
    folder = Column(String(100), default="Bookmarks Bar", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

Index("idx_web_bookmarks_url", WebBookmark.url)

