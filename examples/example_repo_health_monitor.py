#!/usr/bin/env python3
"""
GitKT Repository Health Monitor
================================

A comprehensive real-time monitoring system for Git repository health metrics.
This example demonstrates advanced GitKT usage for:
- Tracking commit frequency and patterns
- Analyzing contributor activity and bus factor
- Measuring code churn and technical debt indicators
- Detecting stale branches and merge conflicts
- Sending automated alerts via webhooks

Requirements:
    pip install gitkt fastapi uvicorn httpx apscheduler pydantic-settings

Usage:
    # Start the monitoring dashboard
    python example_repo_health_monitor.py
    
    # Or run with custom configuration
    GITKT_REPOS="/path/to/repo1,/path/to/repo2" python example_repo_health_monitor.py

Author: GitKT Community
License: MIT
"""

import asyncio
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# GitKT imports - the framework we're demonstrating
from gitkt import Repository, Commit, Branch, Contributor
from gitkt.analysis import (
    CommitAnalyzer,
    ChurnCalculator,
    ContributorGraph,
    BranchHealthChecker,
)
from gitkt.metrics import MetricsCollector, TimeSeriesData
from gitkt.alerts import AlertManager, AlertLevel


# =============================================================================
# Configuration
# =============================================================================

class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Repository configuration
    repos: list[str] = Field(
        default=["."],
        description="Comma-separated list of repository paths to monitor"
    )
    
    # Monitoring thresholds
    min_daily_commits: int = Field(
        default=3,
        description="Minimum expected commits per day"
    )
    max_days_without_commit: int = Field(
        default=3,
        description="Alert if no commits for this many days"
    )
    min_active_contributors: int = Field(
        default=2,
        description="Minimum active contributors (bus factor)"
    )
    max_branch_age_days: int = Field(
        default=30,
        description="Alert for branches older than this"
    )
    max_file_churn_threshold: float = Field(
        default=0.7,
        description="Alert if file changes too frequently (0-1)"
    )
    
    # Alert configuration
    webhook_url: str | None = Field(
        default=None,
        description="Webhook URL for sending alerts (Slack, Discord, etc.)"
    )
    alert_cooldown_minutes: int = Field(
        default=60,
        description="Minimum time between repeated alerts"
    )
    
    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000
    check_interval_minutes: int = 15
    
    class Config:
        env_prefix = "GITKT_"
        env_nested_delimiter = "__"

    @classmethod
    def parse_repos(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [r.strip() for r in v.split(",")]
        return v


settings = Settings()


# =============================================================================
# Domain Models
# =============================================================================

class HealthStatus(str, Enum):
    """Overall health status indicators."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class CommitMetrics:
    """Metrics related to commit activity."""
    total_commits_30d: int = 0
    commits_today: int = 0
    commits_this_week: int = 0
    avg_daily_commits: float = 0.0
    days_since_last_commit: int = 0
    commit_frequency_trend: str = "stable"  # increasing, decreasing, stable
    peak_commit_hours: list[int] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "total_commits_30d": self.total_commits_30d,
            "commits_today": self.commits_today,
            "commits_this_week": self.commits_this_week,
            "avg_daily_commits": round(self.avg_daily_commits, 2),
            "days_since_last_commit": self.days_since_last_commit,
            "commit_frequency_trend": self.commit_frequency_trend,
            "peak_commit_hours": self.peak_commit_hours,
        }


@dataclass
class ContributorMetrics:
    """Metrics related to contributor activity."""
    total_contributors: int = 0
    active_contributors_30d: int = 0
    active_contributors_7d: int = 0
    bus_factor: int = 0  # Contributors responsible for 50% of commits
    top_contributors: list[dict[str, Any]] = field(default_factory=list)
    new_contributors_30d: int = 0
    contributor_diversity_score: float = 0.0  # 0-1, higher is better
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "total_contributors": self.total_contributors,
            "active_contributors_30d": self.active_contributors_30d,
            "active_contributors_7d": self.active_contributors_7d,
            "bus_factor": self.bus_factor,
            "top_contributors": self.top_contributors[:5],
            "new_contributors_30d": self.new_contributors_30d,
            "contributor_diversity_score": round(self.contributor_diversity_score, 2),
        }


@dataclass
class CodeChurnMetrics:
    """Metrics related to code changes and stability."""
    lines_added_30d: int = 0
    lines_deleted_30d: int = 0
    files_changed_30d: int = 0
    avg_commit_size: float = 0.0
    hotspot_files: list[dict[str, Any]] = field(default_factory=list)
    churn_rate: float = 0.0  # Changes per day
    refactor_ratio: float = 0.0  # Deleted/Added ratio
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "lines_added_30d": self.lines_added_30d,
            "lines_deleted_30d": self.lines_deleted_30d,
            "files_changed_30d": self.files_changed_30d,
            "avg_commit_size": round(self.avg_commit_size, 2),
            "hotspot_files": self.hotspot_files[:10],
            "churn_rate": round(self.churn_rate, 2),
            "refactor_ratio": round(self.refactor_ratio, 2),
        }


@dataclass
class BranchMetrics:
    """Metrics related to branch health."""
    total_branches: int = 0
    active_branches: int = 0
    stale_branches: list[dict[str, Any]] = field(default_factory=list)
    unmerged_branches: int = 0
    avg_branch_lifetime_days: float = 0.0
    branches_with_conflicts: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "total_branches": self.total_branches,
            "active_branches": self.active_branches,
            "stale_branches": self.stale_branches[:10],
            "unmerged_branches": self.unmerged_branches,
            "avg_branch_lifetime_days": round(self.avg_branch_lifetime_days, 2),
            "branches_with_conflicts": self.branches_with_conflicts[:5],
        }


@dataclass
class RepositoryHealth:
    """Complete health report for a repository."""
    repo_path: str
    repo_name: str
    status: HealthStatus
    score: int  # 0-100
    last_checked: datetime
    commit_metrics: CommitMetrics
    contributor_metrics: ContributorMetrics
    churn_metrics: CodeChurnMetrics
    branch_metrics: BranchMetrics
    alerts: list[dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_path": self.repo_path,
            "repo_name": self.repo_name,
            "status": self.status.value,
            "score": self.score,
            "last_checked": self.last_checked.isoformat(),
            "commit_metrics": self.commit_metrics.to_dict(),
            "contributor_metrics": self.contributor_metrics.to_dict(),
            "churn_metrics": self.churn_metrics.to_dict(),
            "branch_metrics": self.branch_metrics.to_dict(),
            "alerts": self.alerts,
        }


# =============================================================================
# API Models
# =============================================================================

class AlertConfig(BaseModel):
    """Configuration for alert thresholds."""
    min_daily_commits: int = 3
    max_days_without_commit: int = 3
    min_active_contributors: int = 2
    max_branch_age_days: int = 30


class WebhookPayload(BaseModel):
    """Payload structure for webhook alerts."""
    event_type: str
    repository: str
    severity: str
    message: str
    details: dict[str, Any]
    timestamp: str


# =============================================================================
# Health Monitor Core
# =============================================================================

class RepositoryHealthMonitor:
    """
    Core monitoring class that uses GitKT to analyze repository health.
    
    This class demonstrates comprehensive usage of GitKT's analysis capabilities
    including commit analysis, contributor tracking, and branch health checking.
    """
    
    def __init__(self, repo_path: str):
        """
        Initialize the monitor for a specific repository.
        
        Args:
            repo_path: Path to the Git repository
        """
        self.repo_path = Path(repo_path).resolve()
        self.repo_name = self.repo_path.name
        
        # Initialize GitKT components
        # Repository is the main entry point for all GitKT operations
        self.repo = Repository(str(self.repo_path))
        
        # Analyzers for different aspects of repository health
        self.commit_analyzer = CommitAnalyzer(self.repo)
        self.churn_calculator = ChurnCalculator(self.repo)
        self.contributor_graph = ContributorGraph(self.repo)
        self.branch_checker = BranchHealthChecker(self.repo)
        
        # Metrics collector for time-series data
        self.metrics = MetricsCollector(self.repo)
        
        # Alert manager for threshold-based notifications
        self.alert_manager = AlertManager()
        
    async def analyze_commits(self, days: int = 30) -> CommitMetrics:
        """
        Analyze commit patterns and frequency.
        
        Uses GitKT's CommitAnalyzer to extract meaningful metrics
        about development activity.
        """
        metrics = CommitMetrics()
        
        # Get commits for the analysis period
        since_date = datetime.now() - timedelta(days=days)
        commits = await self.commit_analyzer.get_commits_since(since_date)
        
        metrics.total_commits_30d = len(commits)
        
        # Calculate daily breakdown
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        daily_counts: dict[str, int] = defaultdict(int)
        hourly_counts: dict[int, int] = defaultdict(int)
        
        for commit in commits:
            commit_date = commit.authored_date.date()
            daily_counts[str(commit_date)] += 1
            hourly_counts[commit.authored_date.hour] += 1
            
            if commit_date == today:
                metrics.commits_today += 1
            if commit_date >= week_ago:
                metrics.commits_this_week += 1
        
        # Calculate averages and trends
        if daily_counts:
            metrics.avg_daily_commits = statistics.mean(daily_counts.values())
            
            # Determine trend by comparing recent vs older commits
            recent_avg = statistics.mean(
                [v for k, v in daily_counts.items() 
                 if datetime.fromisoformat(k).date() >= week_ago]
            ) if any(datetime.fromisoformat(k).date() >= week_ago for k in daily_counts) else 0
            
            older_avg = statistics.mean(
                [v for k, v in daily_counts.items()
                 if datetime.fromisoformat(k).date() < week_ago]
            ) if any(datetime.fromisoformat(k).date() < week_ago for k in daily_counts) else 0
            
            if recent_avg > older_avg * 1.2:
                metrics.commit_frequency_trend = "increasing"
            elif recent_avg < older_avg * 0.8:
                metrics.commit_frequency_trend = "decreasing"
        
        # Find peak commit hours
        if hourly_counts:
            sorted_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)
            metrics.peak_commit_hours = [h for h, _ in sorted_hours[:3]]
        
        # Days since last commit
        if commits:
            last_commit = max(commits, key=lambda c: c.authored_date)
            metrics.days_since_last_commit = (datetime.now() - last_commit.authored_date).days
        else:
            metrics.days_since_last_commit = days  # No commits in period
            
        return metrics
    
    async def analyze_contributors(self, days: int = 30) -> ContributorMetrics:
        """
        Analyze contributor activity and calculate bus factor.
        
        Uses GitKT's ContributorGraph to understand team dynamics
        and identify potential knowledge silos.
        """
        metrics = ContributorMetrics()
        
        # Get contributor statistics
        contributors = await self.contributor_graph.get_contributors()
        metrics.total_contributors = len(contributors)
        
        # Analyze activity periods
        since_30d = datetime.now() - timedelta(days=30)
        since_7d = datetime.now() - timedelta(days=7)
        
        active_30d = set()
        active_7d = set()
        commit_counts: dict[str, int] = defaultdict(int)
        
        # Get recent commits for activity analysis
        recent_commits = await self.commit_analyzer.get_commits_since(since_30d)
        
        for commit in recent_commits:
            author_email = commit.author.email
            commit_counts[author_email] += 1
            active_30d.add(author_email)
            
            if commit.authored_date >= since_7d:
                active_7d.add(author_email)
        
        metrics.active_contributors_30d = len(active_30d)
        metrics.active_contributors_7d = len(active_7d)
        
        # Calculate bus factor (contributors responsible for 50% of work)
        if commit_counts:
            total_commits = sum(commit_counts.values())
            sorted_contributors = sorted(
                commit_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            cumulative = 0
            bus_factor = 0
            for email, count