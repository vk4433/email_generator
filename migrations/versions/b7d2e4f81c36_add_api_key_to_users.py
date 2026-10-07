"""add api key (stored hashed) to users for login sessions

Revision ID: b7d2e4f81c36
Revises: a3f1c9d27b45
Create Date: 2026-10-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d2e4f81c36'
down_revision: Union[str, Sequence[str], None] = 'a3f1c9d27b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only the SHA-256 hash of the key is stored; the raw key lives in the user's session.
    op.execute("""
        alter table public.users
            add column api_key_hash text unique,
            add column api_key_created_at timestamptz
    """)

    op.execute("""
        create function public.set_api_key(
            p_user_id bigint,
            p_api_key_hash text
        )
        returns void
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            update public.users
            set api_key_hash = p_api_key_hash,
                api_key_created_at = now()
            where user_id = p_user_id;
        end;
        $$
    """)

    op.execute("""
        create function public.get_user_id_by_api_key(
            p_api_key_hash text,
            p_max_age_seconds integer default 604800
        )
        returns bigint
        language plpgsql
        security definer
        set search_path = public
        as $$
        declare
            matched_id bigint;
        begin
            select user_id into matched_id
            from public.users
            where api_key_hash = p_api_key_hash
                and api_key_created_at > now() - make_interval(secs => p_max_age_seconds);
            return matched_id;
        end;
        $$
    """)

    op.execute("""
        create function public.clear_api_key(p_user_id bigint)
        returns void
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            update public.users
            set api_key_hash = null,
                api_key_created_at = null
            where user_id = p_user_id;
        end;
        $$
    """)

    op.execute("grant execute on function public.set_api_key(bigint, text) to anon")
    op.execute("grant execute on function public.get_user_id_by_api_key(text, integer) to anon")
    op.execute("grant execute on function public.clear_api_key(bigint) to anon")


def downgrade() -> None:
    op.execute("drop function if exists public.clear_api_key(bigint)")
    op.execute("drop function if exists public.get_user_id_by_api_key(text, integer)")
    op.execute("drop function if exists public.set_api_key(bigint, text)")
    op.execute("""
        alter table public.users
            drop column if exists api_key_created_at,
            drop column if exists api_key_hash
    """)
