CREATE TABLE IF NOT EXISTS public.cvjcura_sync_outbox (
    event_id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    operation CHAR(1) NOT NULL CHECK (operation IN ('I', 'U', 'D')),
    row_data JSONB,
    old_data JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT cvjcura_sync_outbox_payload_check CHECK (
        (operation IN ('I', 'U') AND row_data IS NOT NULL)
        OR (operation = 'D' AND old_data IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS cvjcura_sync_outbox_event_idx
    ON public.cvjcura_sync_outbox (event_id);

CREATE OR REPLACE FUNCTION public.cvjcura_capture_sync_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    suppressed TEXT;
BEGIN
    suppressed := current_setting('cvjcura.sync_suppressed', TRUE);
    IF suppressed = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;

    IF TG_OP = 'INSERT' THEN
        INSERT INTO public.cvjcura_sync_outbox
            (table_name, operation, row_data)
        VALUES
            (TG_TABLE_NAME, 'I', to_jsonb(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO public.cvjcura_sync_outbox
            (table_name, operation, row_data, old_data)
        VALUES
            (TG_TABLE_NAME, 'U', to_jsonb(NEW), to_jsonb(OLD));
        RETURN NEW;
    ELSE
        INSERT INTO public.cvjcura_sync_outbox
            (table_name, operation, old_data)
        VALUES
            (TG_TABLE_NAME, 'D', to_jsonb(OLD));
        RETURN OLD;
    END IF;
END;
$$;

DO $$
DECLARE
    sync_table TEXT;
    trigger_name TEXT;
BEGIN
    FOREACH sync_table IN ARRAY ARRAY[
        'acessos',
        'chamada_concluida',
        'consulente',
        'frases',
        'giras',
        'mediuns',
        'prevgira',
        'registros',
        'retorno',
        'retornopref',
        'tratamento',
        'triagem',
        'triagempref'
    ]
    LOOP
        IF to_regclass('public.' || sync_table) IS NOT NULL THEN
            trigger_name := 'cvjcura_sync_' || sync_table;
            EXECUTE format(
                'DROP TRIGGER IF EXISTS %I ON public.%I',
                trigger_name,
                sync_table
            );
            EXECUTE format(
                'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON public.%I
                 FOR EACH ROW EXECUTE FUNCTION public.cvjcura_capture_sync_change()',
                trigger_name,
                sync_table
            );
        END IF;
    END LOOP;
END;
$$;

