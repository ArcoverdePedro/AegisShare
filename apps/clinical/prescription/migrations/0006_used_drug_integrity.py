from django.db import migrations

DRUG_FUNCTION = "rx_guard_used_drug_history"
DRUG_TRIGGER = "rx_drug_used_history_guard"


def create_used_drug_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    drug = apps.get_model("prescription", "Drug")
    request_item = apps.get_model("prescription", "MedicationRequestItem")
    drug_table = quote(drug._meta.db_table)
    request_item_table = quote(request_item._meta.db_table)
    function = quote(DRUG_FUNCTION)

    schema_editor.execute(
        f"""
        CREATE OR REPLACE FUNCTION {function}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM {request_item_table}
                 WHERE drug_id = OLD.id
            ) AND (
                NEW.code IS DISTINCT FROM OLD.code
                OR NEW.name IS DISTINCT FROM OLD.name
                OR NEW.presentation IS DISTINCT FROM OLD.presentation
                OR NEW.strength_text IS DISTINCT FROM OLD.strength_text
                OR NEW.route_hint IS DISTINCT FROM OLD.route_hint
                OR NEW.dispense_unit IS DISTINCT FROM OLD.dispense_unit
            ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Medicamento já utilizado em prescrição não pode ter seus dados históricos reescritos.';
            END IF;

            RETURN NEW;
        END;
        $function$;
        """
    )
    schema_editor.execute(
        f"""
        CREATE TRIGGER {quote(DRUG_TRIGGER)}
        BEFORE UPDATE ON {drug_table}
        FOR EACH ROW
        EXECUTE FUNCTION {function}();
        """
    )


def drop_used_drug_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    drug = apps.get_model("prescription", "Drug")
    schema_editor.execute(
        f"DROP TRIGGER IF EXISTS {quote(DRUG_TRIGGER)} ON {quote(drug._meta.db_table)};"
    )
    schema_editor.execute(f"DROP FUNCTION IF EXISTS {quote(DRUG_FUNCTION)}();")


class Migration(migrations.Migration):
    dependencies = [
        ("prescription", "0005_approved_reference_integrity"),
    ]

    operations = [
        migrations.RunPython(create_used_drug_guard, drop_used_drug_guard),
    ]
