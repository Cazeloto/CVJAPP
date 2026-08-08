CREATE TABLE IF NOT EXISTS public.cvjcura_users (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'operador'
        CHECK (role IN ('admin', 'operador')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMPTZ,
    created_by BIGINT REFERENCES public.cvjcura_users(user_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS cvjcura_users_username_lower_uidx
    ON public.cvjcura_users (lower(username));
