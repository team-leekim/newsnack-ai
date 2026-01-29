from sqlalchemy import Column, Integer, String, Text, ForeignKey, BigInteger, Table, JSON, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base

# 에디터-카테고리 매핑 테이블
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
    category_id = Column(Integer, ForeignKey("category.id"))
    issue_id = Column(BigInteger, ForeignKey("issue.id"))
    
    category = relationship("Category")

class Issue(Base):
    __tablename__ = "issue"
    id = Column(BigInteger, primary_key=True)
    issue_title = Column(String(255))
    category_id = Column(Integer, ForeignKey("category.id"))
    
    # Issue와 연결된 기사들
    articles = relationship("RawArticle", backref="issue")
    category = relationship("Category")

class AiContent(Base):
    __tablename__ = "ai_content"
    id = Column(BigInteger, primary_key=True)
    content_type = Column(String(20)) # WEBTOON, CARD_NEWS
    thumbnail_url = Column(Text)
    
class AiArticle(Base):
    __tablename__ = "ai_article"
    ai_content_id = Column(BigInteger, ForeignKey("ai_content.id"), primary_key=True)
    title = Column(String(255))
    editor_id = Column(Integer, ForeignKey("editor.id"))
    category_id = Column(Integer, ForeignKey("category.id"))
    summary = Column(JSONB)
    body = Column(Text)
    image_data = Column(JSONB)
