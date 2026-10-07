"""add last working day, current salary and expected salary to users

Revision ID: a3f1c9d27b45
Revises: 6cebb4eade06
Create Date: 2026-10-07 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c9d27b45'
down_revision: Union[str, Sequence[str], None] = '6cebb4eade06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        alter table public.users
            add column last_working_day date,
            add column current_salary numeric(12, 2),
            add column expected_salary numeric(12, 2)
    """)

    # Return type and signature changed, so the old functions must be dropped first.
    op.execute("drop function if exists public.get_user_profile(bigint)")
    op.execute("""
        create function public.get_user_profile(p_user_id bigint)
        returns table(
            user_id bigint,
            name text,
            email text,
            resume_pdf text,
            linkedin_url text,
            github_url text,
            last_working_day date,
            current_salary numeric,
            expected_salary numeric
        )
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            return query
            select u.user_id, u.name, u.email, u.resume_pdf, u.linkedin_url, u.github_url,
                   u.last_working_day, u.current_salary, u.expected_salary
            from public.users u
            where u.user_id = p_user_id;
        end;
        $$
    """)

    op.execute("drop function if exists public.update_user_profile(bigint, text, text, text)")
    op.execute("""
        create function public.update_user_profile(
            p_user_id bigint,
            p_name text,
            p_linkedin_url text default null,
            p_github_url text default null,
            p_last_working_day date default null,
            p_current_salary numeric default null,
            p_expected_salary numeric default null
        )
        returns void
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            update public.users
            set name = p_name,
                linkedin_url = p_linkedin_url,
                github_url = p_github_url,
                last_working_day = p_last_working_day,
                current_salary = p_current_salary,
                expected_salary = p_expected_salary
            where user_id = p_user_id;
        end;
        $$
    """)

    op.execute("grant execute on function public.get_user_profile(bigint) to anon")
    op.execute("grant execute on function public.update_user_profile(bigint, text, text, text, date, numeric, numeric) to anon")


def downgrade() -> None:
    op.execute("drop function if exists public.update_user_profile(bigint, text, text, text, date, numeric, numeric)")
    op.execute("drop function if exists public.get_user_profile(bigint)")

    op.execute("""
        create function public.get_user_profile(p_user_id bigint)
        returns table(
            user_id bigint,
            name text,
            email text,
            resume_pdf text,
            linkedin_url text,
            github_url text
        )
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            return query
            select u.user_id, u.name, u.email, u.resume_pdf, u.linkedin_url, u.github_url
            from public.users u
            where u.user_id = p_user_id;
        end;
        $$
    """)

    op.execute("""
        create function public.update_user_profile(
            p_user_id bigint,
            p_name text,
            p_linkedin_url text default null,
            p_github_url text default null
        )
        returns void
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            update public.users
            set name = p_name,
                linkedin_url = p_linkedin_url,
                github_url = p_github_url
            where user_id = p_user_id;
        end;
        $$
    """)

    op.execute("grant execute on function public.get_user_profile(bigint) to anon")
    op.execute("grant execute on function public.update_user_profile(bigint, text, text, text) to anon")

    op.execute("""
        alter table public.users
            drop column if exists expected_salary,
            drop column if exists current_salary,
            drop column if exists last_working_day
    """)
