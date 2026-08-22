"""initial schema

Revision ID: 6cebb4eade06
Revises:
Create Date: 2026-08-22 14:56:58.565237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6cebb4eade06'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        create table public.users (
            user_id bigint generated always as identity primary key,
            name text not null,
            email text not null unique,
            password text not null,
            gmail_password text not null,
            resume_pdf text,
            linkedin_url text,
            github_url text,
            created_at timestamptz not null default now()
        )
    """)

    op.execute("""
        create table public.applications (
            application_id bigint generated always as identity primary key,
            user_id bigint not null references public.users(user_id) on delete cascade,
            company_name text not null,
            role text not null,
            date_of_application date not null default current_date,
            recruiter_email text,
            status smallint not null default 0 check (status in (0, 1)),
            created_at timestamptz not null default now()
        )
    """)

    # Both tables are RLS-locked with no policies: all access goes through the
    # SECURITY DEFINER functions below, granted to the anon/publishable key.
    op.execute("alter table public.users enable row level security")
    op.execute("alter table public.applications enable row level security")

    op.execute("""
        create function public.create_user(
            p_name text,
            p_email text,
            p_password text,
            p_gmail_password text,
            p_resume_pdf text default null,
            p_linkedin_url text default null,
            p_github_url text default null
        )
        returns bigint
        language plpgsql
        security definer
        set search_path = public
        as $$
        declare
            new_id bigint;
        begin
            insert into public.users (name, email, password, gmail_password, resume_pdf, linkedin_url, github_url)
            values (p_name, p_email, p_password, p_gmail_password, p_resume_pdf, p_linkedin_url, p_github_url)
            returning user_id into new_id;
            return new_id;
        end;
        $$
    """)

    op.execute("""
        create function public.verify_user_password(
            p_email text,
            p_password text
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
            where email = p_email
                and password = p_password;
            return matched_id;
        end;
        $$
    """)

    op.execute("""
        create function public.get_gmail_password(p_user_id bigint)
        returns text
        language plpgsql
        security definer
        set search_path = public
        as $$
        declare
            result text;
        begin
            select gmail_password into result
            from public.users
            where user_id = p_user_id;
            return result;
        end;
        $$
    """)

    op.execute("""
        create function public.update_resume_path(
            p_user_id bigint,
            p_resume_pdf text
        )
        returns void
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            update public.users
            set resume_pdf = p_resume_pdf
            where user_id = p_user_id;
        end;
        $$
    """)

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

    op.execute("""
        create function public.update_user_password(
            p_user_id bigint,
            p_password text
        )
        returns void
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            update public.users
            set password = p_password
            where user_id = p_user_id;
        end;
        $$
    """)

    op.execute("""
        create function public.update_gmail_password(
            p_user_id bigint,
            p_gmail_password text
        )
        returns void
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            update public.users
            set gmail_password = p_gmail_password
            where user_id = p_user_id;
        end;
        $$
    """)

    op.execute("""
        create function public.create_application(
            p_user_id bigint,
            p_company_name text,
            p_role text,
            p_recruiter_email text default null,
            p_date_of_application date default current_date
        )
        returns bigint
        language plpgsql
        security definer
        set search_path = public
        as $$
        declare
            new_id bigint;
        begin
            insert into public.applications (user_id, company_name, role, recruiter_email, date_of_application, status)
            values (p_user_id, p_company_name, p_role, p_recruiter_email, p_date_of_application, 0)
            returning application_id into new_id;
            return new_id;
        end;
        $$
    """)

    op.execute("""
        create function public.list_applications(p_user_id bigint)
        returns table(
            application_id bigint,
            company_name text,
            role text,
            date_of_application date,
            recruiter_email text,
            status smallint
        )
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            return query
            select a.application_id, a.company_name, a.role, a.date_of_application, a.recruiter_email, a.status
            from public.applications a
            where a.user_id = p_user_id
            order by a.date_of_application desc, a.application_id desc;
        end;
        $$
    """)

    op.execute("""
        create function public.update_application_status(
            p_application_id bigint,
            p_user_id bigint,
            p_status smallint
        )
        returns void
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            update public.applications
            set status = p_status
            where application_id = p_application_id
                and user_id = p_user_id;
        end;
        $$
    """)

    op.execute("""
        create function public.delete_application(
            p_application_id bigint,
            p_user_id bigint
        )
        returns void
        language plpgsql
        security definer
        set search_path = public
        as $$
        begin
            delete from public.applications
            where application_id = p_application_id
                and user_id = p_user_id;
        end;
        $$
    """)

    op.execute("grant execute on function public.create_user(text, text, text, text, text, text, text) to anon")
    op.execute("grant execute on function public.verify_user_password(text, text) to anon")
    op.execute("grant execute on function public.get_gmail_password(bigint) to anon")
    op.execute("grant execute on function public.update_resume_path(bigint, text) to anon")
    op.execute("grant execute on function public.get_user_profile(bigint) to anon")
    op.execute("grant execute on function public.update_user_profile(bigint, text, text, text) to anon")
    op.execute("grant execute on function public.update_user_password(bigint, text) to anon")
    op.execute("grant execute on function public.update_gmail_password(bigint, text) to anon")
    op.execute("grant execute on function public.create_application(bigint, text, text, text, date) to anon")
    op.execute("grant execute on function public.list_applications(bigint) to anon")
    op.execute("grant execute on function public.update_application_status(bigint, bigint, smallint) to anon")
    op.execute("grant execute on function public.delete_application(bigint, bigint) to anon")

    # Storage: the "resumes" bucket must exist (create it as Private in the dashboard).
    op.execute("""
        create policy "anon can manage resumes bucket"
        on storage.objects for all
        to anon
        using (bucket_id = 'resumes')
        with check (bucket_id = 'resumes')
    """)


def downgrade() -> None:
    op.execute('drop policy if exists "anon can manage resumes bucket" on storage.objects')
    op.execute("drop function if exists public.delete_application(bigint, bigint)")
    op.execute("drop function if exists public.update_application_status(bigint, bigint, smallint)")
    op.execute("drop function if exists public.list_applications(bigint)")
    op.execute("drop function if exists public.create_application(bigint, text, text, text, date)")
    op.execute("drop function if exists public.update_gmail_password(bigint, text)")
    op.execute("drop function if exists public.update_user_password(bigint, text)")
    op.execute("drop function if exists public.update_user_profile(bigint, text, text, text)")
    op.execute("drop function if exists public.get_user_profile(bigint)")
    op.execute("drop function if exists public.update_resume_path(bigint, text)")
    op.execute("drop function if exists public.get_gmail_password(bigint)")
    op.execute("drop function if exists public.verify_user_password(text, text)")
    op.execute("drop function if exists public.create_user(text, text, text, text, text, text, text)")
    op.execute("drop table if exists public.applications")
    op.execute("drop table if exists public.users")
