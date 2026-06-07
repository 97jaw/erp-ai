"""User identity and role-aware behavior context.

Captures who is asking, their permissions, preferences, and assumption level
so responses adapt to super admin, management, and regular users.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class UserContext:
    """Structured identity and behavior profile for the current user."""

    user_id: int
    name: str
    file_id: str

    # Role hierarchy
    primary_role: str
    level: int
    permissions: set[str]

    # Department
    primary_department: str
    departments: list[str]

    # Preferences (from memory)
    preferred_language: str
    preferred_currency: str
    default_date_range: str
    response_style: str

    # History
    last_login: datetime
    typical_queries: list[str]

    def assumption_level(self) -> str:
        """How aggressively should AI make assumptions?"""
        if self.level >= 70:
            return "aggressive"
        if self.level >= 50:
            return "moderate"
        return "conservative"

    def access_breadth(self) -> str:
        """What scope of data can they see?"""
        if "data.all_projects" in self.permissions:
            return "all"
        if "data.own_department_only" in self.permissions:
            return "department"
        return "limited"

    def behavior_rules(self) -> str:
        """Return role-specific instruction string for Claude prompt injection."""
        if self.level >= 70:
            return """
- Resolve ambiguous queries by SEARCHING, not asking
- Show top match + alternatives, do NOT ask for exact name
- Default to all-data view unless specified
- Skip basic clarifications they obviously don't need
- Provide insights, not just data
"""
        if self.level >= 50:
            return """
- Try to resolve, but confirm when ambiguous
- Show top 3 matches if uncertain
- Department-scoped data by default
"""
        return """
- Be explicit about scope and data shown
- Confirm interpretation before fetching
- Educate about available features
"""

    def summary(self) -> str:
        """Format user context for inclusion in Claude system prompt."""
        return f"""
User: {self.name} (File ID: {self.file_id})
Role: {self.primary_role} (level {self.level})
Department: {self.primary_department}
Assumption Level: {self.assumption_level()}
Data Access: {self.access_breadth()}
Language: {self.preferred_language}
Style: {self.response_style}

CRITICAL:
- This user is a {self.primary_role}.
- Apply {self.assumption_level()} assumption level.
- {self.behavior_rules()}
"""
