from django.db import migrations

REQUEST_FUNCTION = "rx_guard_request_history"
REQUEST_TRIGGER = "rx_request_history_guard"


def create_request_history_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    request = apps.get_model("prescription", "MedicationRequest")
    request_table = quote(request._meta.db_table)
    function = quote(REQUEST_FUNCTION)

    schema_editor.execute(
        f"""
        CREATE OR REPLACE FUNCTION {function}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF OLD.status <> 'DRAFT' THEN
                IF NEW.encounter_id IS DISTINCT FROM OLD.encounter_id
                    OR NEW.authored_by_id IS DISTINCT FROM OLD.authored_by_id
                    OR NEW.replaces_id IS DISTINCT FROM OLD.replaces_id
                    OR NEW.created_at IS DISTINCT FROM OLD.created_at
                    OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at
                THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23514',
                        MESSAGE = 'A identidade histórica da prescrição submetida não pode ser reescrita.';
                END IF;
            ELSIF NEW.status <> 'DRAFT' THEN
                IF NEW.encounter_id IS DISTINCT FROM OLD.encounter_id
                    OR NEW.authored_by_id IS DISTINCT FROM OLD.authored_by_id
                    OR NEW.replaces_id IS DISTINCT FROM OLD.replaces_id
                    OR NEW.created_at IS DISTINCT FROM OLD.created_at
                THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23514',
                        MESSAGE = 'A identidade da prescrição não pode ser reescrita durante a submissão.';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $function$;
        """
    )
    schema_editor.execute(
        f"""
        CREATE TRIGGER {quote(REQUEST_TRIGGER)}
        BEFORE UPDATE ON {request_table}
        FOR EACH ROW
        EXECUTE FUNCTION {function}();
        """
    )


def drop_request_history_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    request = apps.get_model("prescription", "MedicationRequest")
    schema_editor.execute(
        f"DROP TRIGGER IF EXISTS {quote(REQUEST_TRIGGER)} ON {quote(request._meta.db_table)};"
    )
    schema_editor.execute(f"DROP FUNCTION IF EXISTS {quote(REQUEST_FUNCTION)}();")


class Migration(migrations.Migration):
    dependencies = [
        ("prescription", "0007_stock_identity_guards"),
    ]

    operations = [
        migrations.RunPython(create_request_history_guard, drop_request_history_guard),
    ]
