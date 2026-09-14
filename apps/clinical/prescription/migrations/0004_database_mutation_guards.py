from django.db import migrations


APPEND_ONLY_MODELS = (
    "MedicationSafetyReview",
    "MedicationSafetyFinding",
    "MedicationDispense",
    "MedicationDispenseItem",
    "StockMovement",
)
APPEND_ONLY_FUNCTION = "rx_guard_append_only_mutation"
REQUEST_ITEM_FUNCTION = "rx_guard_request_item_mutation"
REQUEST_ITEM_TRIGGER = "rx_medicationrequestitem_mutation_guard"


def _append_only_trigger_name(model):
    return f"rx_{model._meta.model_name}_append_only_guard"


def create_database_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    append_only_function = quote(APPEND_ONLY_FUNCTION)
    request_item_function = quote(REQUEST_ITEM_FUNCTION)

    schema_editor.execute(
        f"""
        CREATE OR REPLACE FUNCTION {append_only_function}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                MESSAGE = 'Registro farmacêutico append-only não pode ser alterado ou excluído.';
        END;
        $function$;
        """
    )

    for model_name in APPEND_ONLY_MODELS:
        model = apps.get_model("prescription", model_name)
        table = quote(model._meta.db_table)
        trigger = quote(_append_only_trigger_name(model))
        schema_editor.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION {append_only_function}();
            """
        )

    request_model = apps.get_model("prescription", "MedicationRequest")
    request_item_model = apps.get_model("prescription", "MedicationRequestItem")
    request_table = quote(request_model._meta.db_table)
    request_item_table = quote(request_item_model._meta.db_table)
    request_item_trigger = quote(REQUEST_ITEM_TRIGGER)

    schema_editor.execute(
        f"""
        CREATE OR REPLACE FUNCTION {request_item_function}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        DECLARE
            old_request_status text;
            new_request_status text;
        BEGIN
            SELECT status
              INTO old_request_status
              FROM {request_table}
             WHERE id = OLD.medication_request_id;

            IF old_request_status IS DISTINCT FROM 'DRAFT' THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Item de prescrição só pode ser alterado ou excluído enquanto o estado persistido é DRAFT.';
            END IF;

            IF TG_OP = 'UPDATE' THEN
                SELECT status
                  INTO new_request_status
                  FROM {request_table}
                 WHERE id = NEW.medication_request_id;

                IF new_request_status IS DISTINCT FROM 'DRAFT' THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23514',
                        MESSAGE = 'Item de prescrição não pode ser movido para uma prescrição fora de DRAFT.';
                END IF;
                RETURN NEW;
            END IF;

            RETURN OLD;
        END;
        $function$;
        """
    )
    schema_editor.execute(
        f"""
        CREATE TRIGGER {request_item_trigger}
        BEFORE UPDATE OR DELETE ON {request_item_table}
        FOR EACH ROW
        EXECUTE FUNCTION {request_item_function}();
        """
    )


def drop_database_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name

    request_item_model = apps.get_model("prescription", "MedicationRequestItem")
    schema_editor.execute(
        f"DROP TRIGGER IF EXISTS {quote(REQUEST_ITEM_TRIGGER)} "
        f"ON {quote(request_item_model._meta.db_table)};"
    )

    for model_name in APPEND_ONLY_MODELS:
        model = apps.get_model("prescription", model_name)
        schema_editor.execute(
            f"DROP TRIGGER IF EXISTS {quote(_append_only_trigger_name(model))} "
            f"ON {quote(model._meta.db_table)};"
        )

    schema_editor.execute(f"DROP FUNCTION IF EXISTS {quote(REQUEST_ITEM_FUNCTION)}();")
    schema_editor.execute(f"DROP FUNCTION IF EXISTS {quote(APPEND_ONLY_FUNCTION)}();")


class Migration(migrations.Migration):
    dependencies = [
        ("prescription", "0003_pharmacy_stock"),
    ]

    operations = [
        migrations.RunPython(create_database_guards, drop_database_guards),
    ]
