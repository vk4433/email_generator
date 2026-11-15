"""add user_prompt to users for personalized email instructions

Revision ID: c4e8a1f02d57
Revises: b7d2e4f81c36
Create Date: 2026-11-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a1f02d57'
down_revision: Union[str, Sequence[str], None] = 'b7d2e4f81c36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Free-text writing instructions; null means "use the app's default style".
    op.execute("""
        alter table public.users
            add column user_prompt text
                constraint users_user_prompt_length check (char_length(user_prompt) <= 4000)
    """)

    # Return type changed, so the old function must be dropped first.
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
            expected_salary numeric,
            user_prompt text
        )
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            return query
            select u.user_id, u.name, u.email, u.resume_pdf, u.linkedin_url, u.github_url,
                   u.last_working_day, u.current_salary, u.expected_salary, u.user_prompt
            from public.users u
            where u.user_id = p_user_id;
        end;
        $$
    """)

    op.execute("""
        create function public.update_user_prompt(
            p_user_id bigint,
            p_user_prompt text default null
        )
        returns void
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            update public.users
            set user_prompt = nullif(btrim(p_user_prompt), '')
            where user_id = p_user_id;
        end;
        $$
    """)

    op.execute("grant execute on function public.get_user_profile(bigint) to anon")
    op.execute("grant execute on function public.update_user_prompt(bigint, text) to anon")


def downgrade() -> None:
    op.execute("drop function if exists public.update_user_prompt(bigint, text)")
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
    op.execute("grant execute on function public.get_user_profile(bigint) to anon")

    op.execute("alter table public.users drop column if exists user_prompt")
