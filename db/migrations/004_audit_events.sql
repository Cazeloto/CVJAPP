CREATE TABLE IF NOT EXISTS public.cvjapp_audit_events (
    event_id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor_id BIGINT REFERENCES public.cvjcura_users(user_id) ON DELETE SET NULL,
    actor_label VARCHAR(120) NOT NULL,
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(120),
    outcome VARCHAR(20) NOT NULL DEFAULT 'success'
        CHECK (outcome IN ('success', 'denied', 'failure')),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT cvjapp_audit_action_not_blank CHECK (btrim(action) <> ''),
    CONSTRAINT cvjapp_audit_entity_not_blank CHECK (btrim(entity_type) <> ''),
    CONSTRAINT cvjapp_audit_actor_not_blank CHECK (btrim(actor_label) <> '')
);

CREATE INDEX IF NOT EXISTS cvjapp_audit_events_occurred_idx
    ON public.cvjapp_audit_events (occurred_at DESC, event_id DESC);

CREATE INDEX IF NOT EXISTS cvjapp_audit_events_actor_idx
    ON public.cvjapp_audit_events (actor_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS cvjapp_audit_events_action_idx
    ON public.cvjapp_audit_events (action, occurred_at DESC);
