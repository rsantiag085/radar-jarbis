begin;

-- UUIDs are used for entities that may be exposed outside the database.
-- gen_random_uuid() is available in current Supabase Postgres projects.

create table public.marketplaces (
    id bigint generated always as identity primary key,
    code text not null,
    name text not null,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint marketplaces_code_key unique (code),
    constraint marketplaces_code_not_blank check (btrim(code) <> ''),
    constraint marketplaces_name_not_blank check (btrim(name) <> '')
);

create table public.sources (
    id bigint generated always as identity primary key,
    source_type text not null,
    external_id text not null,
    name text,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint sources_type_external_id_key unique (source_type, external_id),
    constraint sources_source_type_not_blank check (btrim(source_type) <> ''),
    constraint sources_external_id_not_blank check (btrim(external_id) <> '')
);

create table public.products (
    id uuid primary key default gen_random_uuid(),
    marketplace_id bigint not null references public.marketplaces(id) on delete restrict,
    external_product_id text not null,
    asin text,
    title text not null,
    image_url text,
    original_url text,
    affiliate_url text,
    status text not null default 'active',
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint products_marketplace_external_id_key
        unique (marketplace_id, external_product_id),
    constraint products_external_product_id_not_blank
        check (btrim(external_product_id) <> ''),
    constraint products_title_not_blank check (btrim(title) <> ''),
    constraint products_status_check
        check (status in ('active', 'inactive', 'unavailable', 'archived')),
    constraint products_seen_at_order_check check (last_seen_at >= first_seen_at)
);

create table public.offers (
    id bigint generated always as identity primary key,
    product_id uuid not null references public.products(id) on delete cascade,
    current_price numeric(14, 2) not null,
    previous_price numeric(14, 2),
    discount_percentage numeric(7, 4),
    currency text not null default 'BRL',
    captured_at timestamptz not null default now(),
    constraint offers_current_price_nonnegative check (current_price >= 0),
    constraint offers_previous_price_nonnegative
        check (previous_price is null or previous_price >= 0),
    constraint offers_discount_percentage_range
        check (
            discount_percentage is null
            or discount_percentage between 0 and 100
        ),
    constraint offers_currency_format check (currency ~ '^[A-Z]{3}$')
);

create table public.captured_messages (
    id bigint generated always as identity primary key,
    source_id bigint not null references public.sources(id) on delete restrict,
    telegram_chat_id bigint not null,
    telegram_message_id bigint not null,
    product_id uuid references public.products(id) on delete set null,
    raw_text text,
    formatted_text text,
    captured_at timestamptz not null default now(),
    constraint captured_messages_telegram_key
        unique (telegram_chat_id, telegram_message_id)
);

create table public.content_items (
    id uuid primary key default gen_random_uuid(),
    product_id uuid references public.products(id) on delete set null,
    content_type text not null,
    content_text text,
    script_json jsonb,
    keyword text,
    status text not null default 'draft',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint content_items_content_type_not_blank check (btrim(content_type) <> ''),
    constraint content_items_status_check
        check (status in ('draft', 'ready', 'archived')),
    constraint content_items_script_json_object_check
        check (script_json is null or jsonb_typeof(script_json) = 'object')
);

create table public.publications (
    id uuid primary key default gen_random_uuid(),
    content_item_id uuid not null references public.content_items(id) on delete restrict,
    platform text not null,
    publication_type text not null,
    scheduled_at timestamptz,
    published_at timestamptz,
    external_post_id text,
    status text not null default 'pending',
    error_message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint publications_platform_not_blank check (btrim(platform) <> ''),
    constraint publications_type_not_blank check (btrim(publication_type) <> ''),
    constraint publications_status_check
        check (status in ('pending', 'scheduled', 'published', 'failed', 'cancelled'))
);

-- Foreign keys are not indexed automatically by Postgres. These indexes cover
-- joins, deletes and the expected chronological access patterns.
create index products_marketplace_id_idx
    on public.products (marketplace_id);
create index products_asin_idx
    on public.products (asin)
    where asin is not null;
create index offers_product_captured_at_idx
    on public.offers (product_id, captured_at desc);
create index captured_messages_source_id_idx
    on public.captured_messages (source_id);
create index captured_messages_product_id_idx
    on public.captured_messages (product_id)
    where product_id is not null;
create index captured_messages_captured_at_idx
    on public.captured_messages (captured_at desc);
create index content_items_product_id_idx
    on public.content_items (product_id)
    where product_id is not null;
create index content_items_status_created_at_idx
    on public.content_items (status, created_at desc);
create index publications_content_item_id_idx
    on public.publications (content_item_id);
create index publications_status_scheduled_at_idx
    on public.publications (status, scheduled_at)
    where scheduled_at is not null;

-- updated_at is maintained centrally so every writer follows the same rule.
create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger marketplaces_set_updated_at
before update on public.marketplaces
for each row execute function public.set_updated_at();

create trigger sources_set_updated_at
before update on public.sources
for each row execute function public.set_updated_at();

create trigger products_set_updated_at
before update on public.products
for each row execute function public.set_updated_at();

create trigger content_items_set_updated_at
before update on public.content_items
for each row execute function public.set_updated_at();

create trigger publications_set_updated_at
before update on public.publications
for each row execute function public.set_updated_at();

-- public is exposed by Supabase's Data API. RLS is enabled without client
-- policies intentionally: anon/authenticated receive no row access until a
-- later migration defines an explicit access model. Backend privileged keys
-- must remain server-side only.
alter table public.marketplaces enable row level security;
alter table public.sources enable row level security;
alter table public.products enable row level security;
alter table public.offers enable row level security;
alter table public.captured_messages enable row level security;
alter table public.content_items enable row level security;
alter table public.publications enable row level security;

-- Initial marketplace. Additional marketplaces can be added without changing
-- product identity because external IDs are scoped by marketplace_id.
insert into public.marketplaces (code, name)
values ('amazon_br', 'Amazon Brasil');

commit;
