begin;

-- Destructive rollback: dependent tables are removed before their parents.
drop table if exists public.publications;
drop table if exists public.content_items;
drop table if exists public.captured_messages;
drop table if exists public.offers;
drop table if exists public.products;
drop table if exists public.sources;
drop table if exists public.marketplaces;
drop function if exists public.set_updated_at();

commit;
