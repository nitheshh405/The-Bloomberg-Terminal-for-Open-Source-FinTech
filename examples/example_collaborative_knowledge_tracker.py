#!/usr/bin/env python3
"""
GitKT Framework - Collaborative Knowledge Tracker Example

This example demonstrates a real-world use case for GitKT: building a system
that captures and transfers institutional knowledge from collaborative document
editing sessions. Perfect for:

- Onboarding new team members with context-rich documentation
- Preserving decision rationale when team members leave
- Creating searchable knowledge bases from organic team discussions
- Tracking the evolution of technical decisions over time

Requirements:
    pip install gitkt fastapi uvicorn websockets aiosqlite pydantic

Usage:
    python example_collaborative_knowledge_tracker.py
    
    Then open http://localhost:8000/docs for the interactive API.
"""

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# =============================================================================
# GitKT Core Integration
# =============================================================================

class KnowledgeType(str, Enum):
    """Categories of knowledge that can be captured and transferred."""
    DECISION = "decision"           # Why something was decided
    CONTEXT = "context"             # Background information
    PROCEDURE = "procedure"         # How to do something
    LESSON_LEARNED = "lesson"       # What we learned from experience
    REFERENCE = "reference"         # Links to external resources
    DISCUSSION = "discussion"       # Team conversation summaries


class KnowledgeEntry(BaseModel):
    """A single piece of transferable knowledge."""
    id: str = Field(default="", description="Unique identifier (auto-generated)")
    document_id: str = Field(..., description="Associated document ID")
    knowledge_type: KnowledgeType = Field(..., description="Category of knowledge")
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    author: str = Field(..., description="Who contributed this knowledge")
    tags: list[str] = Field(default_factory=list)
    parent_id: Optional[str] = Field(default=None, description="For threaded discussions")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(default=1)
    
    def generate_id(self) -> str:
        """Generate a content-addressable ID (GitKT pattern)."""
        content_hash = hashlib.sha256(
            f"{self.document_id}:{self.title}:{self.content}:{self.created_at.isoformat()}".encode()
        ).hexdigest()[:12]
        return f"kt-{content_hash}"


class DocumentChange(BaseModel):
    """Represents a change to a collaborative document."""
    document_id: str
    section: str
    old_content: Optional[str] = None
    new_content: str
    change_type: str  # "addition", "modification", "deletion"
    author: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    extracted_knowledge: list[KnowledgeEntry] = Field(default_factory=list)


class KnowledgeQuery(BaseModel):
    """Query parameters for searching the knowledge base."""
    keywords: Optional[str] = None
    knowledge_types: Optional[list[KnowledgeType]] = None
    authors: Optional[list[str]] = None
    document_ids: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(default=50, le=200)


class TransferReport(BaseModel):
    """Knowledge transfer report for team transitions."""
    team_member: str
    transfer_date: datetime
    knowledge_entries: list[KnowledgeEntry]
    related_documents: list[str]
    key_decisions: list[str]
    recommended_contacts: list[str]
    coverage_score: float  # How much of their knowledge is documented


# =============================================================================
# Database Layer (GitKT-style versioned storage)
# =============================================================================

class KnowledgeDatabase:
    """
    SQLite-based knowledge store with GitKT versioning patterns.
    
    Implements:
    - Content-addressable storage for knowledge entries
    - Full version history for audit trails
    - Efficient full-text search
    - Relationship tracking between knowledge pieces
    """
    
    def __init__(self, db_path: str = "knowledge_base.db"):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Initialize database connection and schema."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_schema()
    
    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
    
    async def _create_schema(self):
        """Create GitKT-optimized schema for knowledge tracking."""
        await self._connection.executescript("""
            -- Main knowledge entries table
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                knowledge_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                parent_id TEXT,
                created_at TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                is_current INTEGER DEFAULT 1,
                FOREIGN KEY (parent_id) REFERENCES knowledge_entries(id)
            );
            
            -- Version history for GitKT-style tracking
            CREATE TABLE IF NOT EXISTS knowledge_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                content_snapshot TEXT NOT NULL,
                changed_by TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                change_reason TEXT,
                FOREIGN KEY (entry_id) REFERENCES knowledge_entries(id)
            );
            
            -- Document change log for context
            CREATE TABLE IF NOT EXISTS document_changes (
                change_id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                section TEXT,
                change_type TEXT NOT NULL,
                author TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                content_diff TEXT
            );
            
            -- Full-text search index
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                id,
                title,
                content,
                tags,
                author,
                content='knowledge_entries'
            );
            
            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS knowledge_fts_insert 
            AFTER INSERT ON knowledge_entries BEGIN
                INSERT INTO knowledge_fts(id, title, content, tags, author)
                VALUES (new.id, new.title, new.content, new.tags, new.author);
            END;
            
            CREATE TRIGGER IF NOT EXISTS knowledge_fts_update
            AFTER UPDATE ON knowledge_entries BEGIN
                UPDATE knowledge_fts 
                SET title = new.title, content = new.content, 
                    tags = new.tags, author = new.author
                WHERE id = new.id;
            END;
            
            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_knowledge_document 
                ON knowledge_entries(document_id);
            CREATE INDEX IF NOT EXISTS idx_knowledge_author 
                ON knowledge_entries(author);
            CREATE INDEX IF NOT EXISTS idx_knowledge_type 
                ON knowledge_entries(knowledge_type);
            CREATE INDEX IF NOT EXISTS idx_knowledge_created 
                ON knowledge_entries(created_at);
        """)
        await self._connection.commit()
    
    async def store_knowledge(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        """
        Store a knowledge entry with GitKT versioning.
        
        If an entry with the same ID exists, creates a new version
        while preserving history.
        """
        if not entry.id:
            entry.id = entry.generate_id()
        
        # Check if this is an update
        existing = await self.get_knowledge(entry.id)
        
        if existing:
            # Archive current version to history
            await self._connection.execute("""
                INSERT INTO knowledge_history 
                (entry_id, version, content_snapshot, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                existing.id,
                existing.version,
                existing.model_dump_json(),
                entry.author,
                datetime.now(timezone.utc).isoformat()
            ))
            
            entry.version = existing.version + 1
            
            # Update existing entry
            await self._connection.execute("""
                UPDATE knowledge_entries 
                SET title = ?, content = ?, tags = ?, version = ?
                WHERE id = ?
            """, (
                entry.title,
                entry.content,
                json.dumps(entry.tags),
                entry.version,
                entry.id
            ))
        else:
            # Insert new entry
            await self._connection.execute("""
                INSERT INTO knowledge_entries 
                (id, document_id, knowledge_type, title, content, author, 
                 tags, parent_id, created_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.document_id,
                entry.knowledge_type.value,
                entry.title,
                entry.content,
                entry.author,
                json.dumps(entry.tags),
                entry.parent_id,
                entry.created_at.isoformat(),
                entry.version
            ))
        
        await self._connection.commit()
        return entry
    
    async def get_knowledge(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Retrieve a knowledge entry by ID."""
        cursor = await self._connection.execute(
            "SELECT * FROM knowledge_entries WHERE id = ? AND is_current = 1",
            (entry_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            return self._row_to_entry(row)
        return None
    
    async def search_knowledge(self, query: KnowledgeQuery) -> list[KnowledgeEntry]:
        """
        Search knowledge base with multiple filters.
        
        Supports full-text search, type filtering, author filtering,
        date ranges, and tag matching.
        """
        conditions = ["ke.is_current = 1"]
        params = []
        
        # Full-text search
        if query.keywords:
            conditions.append("""
                ke.id IN (
                    SELECT id FROM knowledge_fts 
                    WHERE knowledge_fts MATCH ?
                )
            """)
            params.append(query.keywords)
        
        # Type filter
        if query.knowledge_types:
            placeholders = ",".join("?" * len(query.knowledge_types))
            conditions.append(f"ke.knowledge_type IN ({placeholders})")
            params.extend([kt.value for kt in query.knowledge_types])
        
        # Author filter
        if query.authors:
            placeholders = ",".join("?" * len(query.authors))
            conditions.append(f"ke.author IN ({placeholders})")
            params.extend(query.authors)
        
        # Document filter
        if query.document_ids:
            placeholders = ",".join("?" * len(query.document_ids))
            conditions.append(f"ke.document_id IN ({placeholders})")
            params.extend(query.document_ids)
        
        # Date range
        if query.date_from:
            conditions.append("ke.created_at >= ?")
            params.append(query.date_from.isoformat())
        
        if query.date_to:
            conditions.append("ke.created_at <= ?")
            params.append(query.date_to.isoformat())
        
        # Tag filter (JSON array search)
        if query.tags:
            tag_conditions = []
            for tag in query.tags:
                tag_conditions.append("ke.tags LIKE ?")
                params.append(f'%"{tag}"%')
            conditions.append(f"({' OR '.join(tag_conditions)})")
        
        sql = f"""
            SELECT ke.* FROM knowledge_entries ke
            WHERE {' AND '.join(conditions)}
            ORDER BY ke.created_at DESC
            LIMIT ?
        """
        params.append(query.limit)
        
        cursor = await self._connection.execute(sql, params)
        rows = await cursor.fetchall()
        
        return [self._row_to_entry(row) for row in rows]
    
    async def get_version_history(self, entry_id: str) -> list[dict]:
        """Get complete version history for a knowledge entry."""
        cursor = await self._connection.execute("""
            SELECT * FROM knowledge_history 
            WHERE entry_id = ?
            ORDER BY version DESC
        """, (entry_id,))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def generate_transfer_report(
        self, 
        team_member: str
    ) -> TransferReport:
        """
        Generate a comprehensive knowledge transfer report.
        
        This is the core GitKT use case: when a team member leaves,
        we can generate a complete report of their institutional knowledge.
        """
        # Get all knowledge contributed by this member
        cursor = await self._connection.execute("""
            SELECT * FROM knowledge_entries 
            WHERE author = ? AND is_current = 1
            ORDER BY created_at DESC
        """, (team_member,))
        
        rows = await cursor.fetchall()
        entries = [self._row_to_entry(row) for row in rows]
        
        # Get related documents
        documents = list(set(e.document_id for e in entries))
        
        # Extract key decisions
        decisions = [
            e.title for e in entries 
            if e.knowledge_type == KnowledgeType.DECISION
        ]
        
        # Find collaborators (potential contacts for follow-up)
        cursor = await self._connection.execute("""
            SELECT DISTINCT author FROM knowledge_entries
            WHERE document_id IN (
                SELECT DISTINCT document_id FROM knowledge_entries
                WHERE author = ?
            ) AND author != ?
            LIMIT 10
        """, (team_member, team_member))
        
        collaborators = [row[0] for row in await cursor.fetchall()]
        
        # Calculate coverage score (simplified metric)
        # In production, this would be more sophisticated
        total_docs = len(documents)
        documented_decisions = len(decisions)
        coverage = min(1.0, (documented_decisions * 0.3 + total_docs * 0.1))
        
        return TransferReport(
            team_member=team_member,
            transfer_date=datetime.now(timezone.utc),
            knowledge_entries=entries,
            related_documents=documents,
            key_decisions=decisions[:10],
            recommended_contacts=collaborators,
            coverage_score=coverage
        )
    
    def _row_to_entry(self, row) -> KnowledgeEntry:
        """Convert database row to KnowledgeEntry model."""
        return KnowledgeEntry(
            id=row["id"],
            document_id=row["document_id"],
            knowledge_type=KnowledgeType(row["knowledge_type"]),
            title=row["title"],
            content=row["content"],
            author=row["author"],
            tags=json.loads(row["tags"]),
            parent_id=row["parent_id"],
            created_at=datetime.fromisoformat(row["