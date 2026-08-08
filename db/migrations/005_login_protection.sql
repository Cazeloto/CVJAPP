ALTER TABLE public.cvjcura_users
    ADD COLUMN IF NOT EXISTS failed_login_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_failed_login_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'cvjcura_users_failed_login_nonnegative'
           AND conrelid = 'public.cvjcura_users'::regclass
    ) THEN
        ALTER TABLE public.cvjcura_users
            ADD CONSTRAINT cvjcura_users_failed_login_nonnegative
            CHECK (failed_login_count >= 0);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'cvjcura_users_auth_version_positive'
           AND conrelid = 'public.cvjcura_users'::regclass
    ) THEN
        ALTER TABLE public.cvjcura_users
            ADD CONSTRAINT cvjcura_users_auth_version_positive
            CHECK (auth_version > 0);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS cvjcura_users_locked_until_idx
    ON public.cvjcura_users (locked_until)
    WHERE locked_until IS NOT NULL;
