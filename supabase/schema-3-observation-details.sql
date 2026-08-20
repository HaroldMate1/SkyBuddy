-- =====================================================================
-- SkyBuddy — third migration: itinerary detail on each observation
-- Run after the first two. Safe to re-run.
--
-- Google Flights returns the operating aircraft and flight numbers per leg.
-- Keeping them with the price is what lets the seat advisory work from a
-- tracked route rather than only from a fresh search.
-- =====================================================================

alter table public.price_observations
  add column if not exists aircraft          text,
  add column if not exists flight_numbers    text,
  add column if not exists duration_minutes  integer,
  add column if not exists stops             integer;

comment on column public.price_observations.duration_minutes is
  'Outbound duration only, so the 8-hour long-haul rule is not fooled by a round trip.';
