-- =====================================================================
-- SkyBuddy — Supabase schema
-- Run this once in the Supabase SQL editor (Dashboard → SQL → New query).
-- Safe to re-run: everything is created with IF NOT EXISTS / OR REPLACE.
-- =====================================================================

-- ---------------------------------------------------------------------
-- profiles: one row per signed-up traveller
-- ---------------------------------------------------------------------
create table if not exists public.profiles (
  id            uuid primary key references auth.users on delete cascade,
  email         text,
  display_name  text,
  home_airport  text,
  currency      text not null default 'EUR',
  email_alerts  boolean not null default true,
  created_at    timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles are self-service" on public.profiles;
create policy "profiles are self-service" on public.profiles
  for all using (auth.uid() = id) with check (auth.uid() = id);

-- create the profile automatically when someone signs up
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'display_name', split_part(new.email, '@', 1))
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------
-- tracked_flights: the routes a traveller is watching
-- ---------------------------------------------------------------------
create table if not exists public.tracked_flights (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references auth.users on delete cascade,
  label             text,
  origin            text not null check (char_length(origin) = 3),
  destination       text not null check (char_length(destination) = 3),
  outbound_date     date not null,
  return_date       date,
  passengers        integer not null default 1 check (passengers between 1 and 9),
  cabin             text not null default 'economy',
  currency          text not null default 'EUR',
  target_price      numeric(10, 2),
  active            boolean not null default true,
  -- rolling statistics, refreshed by every price check
  last_price        numeric(10, 2),
  lowest_price      numeric(10, 2),
  highest_price     numeric(10, 2),
  median_price      numeric(10, 2),
  last_airline      text,
  last_booking_url  text,
  last_checked_at   timestamptz,
  created_at        timestamptz not null default now()
);

create index if not exists tracked_flights_user_idx on public.tracked_flights (user_id);
create index if not exists tracked_flights_active_idx on public.tracked_flights (active) where active;

alter table public.tracked_flights enable row level security;

drop policy if exists "tracked flights are self-service" on public.tracked_flights;
create policy "tracked flights are self-service" on public.tracked_flights
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------
-- price_observations: the history behind every verdict
-- ---------------------------------------------------------------------
create table if not exists public.price_observations (
  id                 bigint generated always as identity primary key,
  tracked_flight_id  uuid not null references public.tracked_flights on delete cascade,
  user_id            uuid not null references auth.users on delete cascade,
  price              numeric(10, 2) not null check (price > 0),
  currency           text not null default 'EUR',
  airline            text,
  booking_url        text,
  source             text not null default 'duffel',
  observed_at        timestamptz not null default now()
);

create index if not exists price_observations_flight_idx
  on public.price_observations (tracked_flight_id, observed_at desc);

alter table public.price_observations enable row level security;

drop policy if exists "observations are readable by their owner" on public.price_observations;
create policy "observations are readable by their owner" on public.price_observations
  for select using (auth.uid() = user_id);

-- ---------------------------------------------------------------------
-- alerts: what was raised, and whether the email went out
-- ---------------------------------------------------------------------
create table if not exists public.alerts (
  id                 bigint generated always as identity primary key,
  tracked_flight_id  uuid not null references public.tracked_flights on delete cascade,
  user_id            uuid not null references auth.users on delete cascade,
  kind               text not null check (kind in ('target_reached', 'new_low', 'price_drop')),
  price              numeric(10, 2) not null,
  previous_price     numeric(10, 2),
  currency           text not null default 'EUR',
  message            text,
  booking_url        text,
  emailed_at         timestamptz,
  created_at         timestamptz not null default now()
);

create index if not exists alerts_user_idx on public.alerts (user_id, created_at desc);
create index if not exists alerts_flight_kind_idx on public.alerts (tracked_flight_id, kind, created_at desc);

alter table public.alerts enable row level security;

drop policy if exists "alerts are readable by their owner" on public.alerts;
create policy "alerts are readable by their owner" on public.alerts
  for select using (auth.uid() = user_id);

-- ---------------------------------------------------------------------
-- Notes
-- * The cron job writes with the service-role key, which bypasses RLS.
-- * Clients only ever use the anon key, so every read and write above is
--   scoped to the signed-in traveller by the policies.
-- ---------------------------------------------------------------------
