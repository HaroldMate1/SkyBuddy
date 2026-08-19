-- =====================================================================
-- SkyBuddy — second migration: booking intents, wallet and passengers
-- Run after supabase/schema.sql, in the Supabase SQL editor.
-- Safe to re-run.
-- =====================================================================

-- ---------------------------------------------------------------------
-- booking_intents: the purchase trigger, online
-- Mirrors scripts/booking_agent.py — nothing executes until the traveller
-- confirms, and the agreed ceiling is re-checked at confirmation.
-- ---------------------------------------------------------------------
create table if not exists public.booking_intents (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references auth.users on delete cascade,
  tracked_flight_id  uuid references public.tracked_flights on delete set null,
  status             text not null default 'awaiting_confirmation'
                     check (status in ('awaiting_confirmation','ready_to_execute','in_progress','booked','cancelled','failed')),
  booking_url        text not null,
  airline            text,
  flight_numbers     text,
  aircraft           text,
  duration_minutes   integer default 0,
  origin             text not null,
  destination        text not null,
  outbound_date      date not null,
  return_date        date,
  cabin              text not null default 'economy',
  price              numeric(10, 2) not null,
  currency           text not null default 'EUR',
  max_price          numeric(10, 2),
  allow_payment      boolean not null default false,
  passengers         text[] default '{}',
  notes              text,
  warnings           text[] default '{}',
  approved_by        text,
  approved_at        timestamptz,
  executed_at        timestamptz,
  confirmation_code  text,
  amount_paid        numeric(10, 2),
  history            jsonb not null default '[]'::jsonb,
  created_at         timestamptz not null default now()
);

create index if not exists booking_intents_user_idx on public.booking_intents (user_id, created_at desc);

alter table public.booking_intents enable row level security;

drop policy if exists "booking intents are self-service" on public.booking_intents;
create policy "booking intents are self-service" on public.booking_intents
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------
-- loyalty_cards: cards and programmes used to estimate points on a fare
-- ---------------------------------------------------------------------
create table if not exists public.loyalty_cards (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references auth.users on delete cascade,
  card_id            text not null,
  issuer             text not null,
  product            text not null,
  network            text,
  points_per_unit    numeric(6, 2) not null default 1,
  programme          text,
  balance            integer default 0,
  tier               text,
  transfer_partners  text[] default '{}',
  notes              text,
  created_at         timestamptz not null default now(),
  unique (user_id, card_id)
);

create index if not exists loyalty_cards_user_idx on public.loyalty_cards (user_id);

alter table public.loyalty_cards enable row level security;

drop policy if exists "loyalty cards are self-service" on public.loyalty_cards;
create policy "loyalty cards are self-service" on public.loyalty_cards
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------
-- passengers: traveller profiles the booking checklist fills from
-- ---------------------------------------------------------------------
create table if not exists public.passengers (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users on delete cascade,
  name            text not null,
  given_name      text not null,
  family_name     text not null,
  born_on         date,
  gender          text,
  title           text default 'mr',
  email           text,
  phone_number    text,
  passport        text,
  nationality     text,
  frequent_flyer  jsonb not null default '{}'::jsonb,
  created_at      timestamptz not null default now(),
  unique (user_id, name)
);

create index if not exists passengers_user_idx on public.passengers (user_id);

alter table public.passengers enable row level security;

drop policy if exists "passengers are self-service" on public.passengers;
create policy "passengers are self-service" on public.passengers
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
