from sqlalchemy import Column, Integer, String, Text, ForeignKey, BigInteger, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base

class EditorCategory(Base):
    __tablename__ = "editor_category"
    id = Column(BigInteger, primary_key=True, index=True)
    editor_id = Column(Integer, ForeignKey("editor.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("category.id"), nullable=False)

class Category(Base):
    __tablename__ = "category"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

class Editor(Base):
    __tablename__ = "editor"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    profile_image_url = Column(Text)
    description = Column(Text)
    keywords = Column(JSONB)
    persona_prompt = Column(Text)

    # N:M 관계
    categories = relationship("Category", secondary="editor_category", backref="editors")

class RawArticle(Base):
    __tablename__ = "raw_article"
    id = Column(BigInteger, primary_key=True)
    title = Column(String(500))
    content = Column(Text)
    origin_url = Column(Text, nullable=False, unique=True) 
    source = Column(String(50), nullable=False)
    category_id = Column(Integer, ForeignKey("category.id"))
    issue_id = Column(BigInteger, ForeignKey("issue.id"))
    published_at = Column(DateTime(timezone=True), nullable=False)
    crawled_at = Column(DateTime(timezone=True), server_default=func.now())
    
    category = relationship("Category")

class Issue(Base):
    __tablename__ = "issue"
    id = Column(BigInteger, primary_key=True)
    issue_title = Column(String(255))
    category_id = Column(Integer, ForeignKey("category.id"))
    batch_time = Column(DateTime(timezone=True), nullable=False)
    is_processed = Column(Boolean, default=False)
    
    articles = relationship("RawArticle", back_populates="issue_obj")
    category = relationship("Category")

    RawArticle.issue_obj = relationship("Issue", back_populates="articles")

class AiArticle(Base):
    __tablename__ = "ai_article"
    id = Column(BigInteger, primary_key=True, index=True)
    issue_id = Column(BigInteger)
    content_type = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    thumbnail_url = Column(Text)
    editor_id = Column(Integer, ForeignKey("editor.id"))
    category_id = Column(Integer, ForeignKey("category.id"))
    summary = Column(JSONB)
    body = Column(Text)
    image_data = Column(JSONB)
    origin_articles = Column(JSONB)
    published_at = Column(DateTime(timezone=True), server_default=func.now())

class ReactionCount(Base):
    __tablename__ = "reaction_count"
    article_id = Column(BigInteger, ForeignKey("ai_article.id"), primary_key=True)
    happy_count = Column(Integer, default=0)
    surprised_count = Column(Integer, default=0)
    sad_count = Column(Integer, default=0)
    angry_count = Column(Integer, default=0)
    empathy_count = Column(Integer, default=0)
