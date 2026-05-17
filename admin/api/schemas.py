from __future__ import annotations

from pydantic import BaseModel, Field


class CreateUserBody(BaseModel):
    file_id: str
    name: str
    email: str | None = None
    language: str = "en"
    role_name: str = "user"
    department_code: str | None = None


class UpdateUserBody(BaseModel):
    name: str | None = None
    email: str | None = None
    language: str | None = None
    name_arabic: str | None = None
    phone: str | None = None
    is_active: bool | None = None
    is_super_admin: bool | None = None


class CreateRoleBody(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    display_name: str
    display_name_ar: str | None = None
    description: str | None = None
    level: int = Field(ge=1, le=99)


class UpdateRoleBody(BaseModel):
    display_name: str | None = None
    display_name_ar: str | None = None
    description: str | None = None
    level: int | None = Field(default=None, ge=1, le=99)


class CreateDepartmentBody(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str
    name_arabic: str | None = None
    parent_id: int | None = None
    description: str | None = None


class UpdateDepartmentBody(BaseModel):
    name: str | None = None
    name_arabic: str | None = None
    parent_id: int | None = None
    description: str | None = None
    is_active: bool | None = None


class DepartmentUserBody(BaseModel):
    user_id: int
    is_primary: bool = False


class CreateFeatureFlagBody(BaseModel):
    code: str
    name: str
    description: str | None = None
    is_enabled: bool = True
    rollout_percent: int = Field(default=100, ge=0, le=100)


class UpdateFeatureFlagBody(BaseModel):
    name: str | None = None
    description: str | None = None
    is_enabled: bool | None = None
    rollout_percent: int | None = Field(default=None, ge=0, le=100)


class AssignRoleBody(BaseModel):
    role_id: int


class GrantPermissionBody(BaseModel):
    permission_id: int
