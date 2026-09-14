from django.db import migrations

INTERACTION_FUNCTION = "rx_guard_approved_interaction"
DOSE_RULE_FUNCTION = "rx_guard_approved_dose_rule"
INTERACTION_TRIGGER = "rx_interaction_approved_reference_guard"
DOSE_RULE_TRIGGER = "rx_doserule_approved_reference_guard"


def create_reference_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    interaction = apps.get_model("prescription", "Interaction")
    dose_rule = apps.get_model("prescription", "DoseRule")
    interaction_table = quote(interaction._meta.db_table)
    dose_rule_table = quote(dose_rule._meta.db_table)
    interaction_function = quote(INTERACTION_FUNCTION)
    dose_rule_function = quote(DOSE_RULE_FUNCTION)

    schema_editor.execute(
        f"""
        CREATE OR REPLACE FUNCTION {interaction_function}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF OLD.approved_at IS NULL THEN
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END IF;

            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Referência de interação aprovada não pode ser excluída.';
            END IF;

            IF OLD.active = FALSE AND NEW.active = TRUE THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Referência de interação aprovada e desativada exige nova versão.';
            END IF;

            IF NEW.drug_a_id IS DISTINCT FROM OLD.drug_a_id
                OR NEW.drug_b_id IS DISTINCT FROM OLD.drug_b_id
                OR NEW.severity IS DISTINCT FROM OLD.severity
                OR NEW.blocking IS DISTINCT FROM OLD.blocking
                OR NEW.summary IS DISTINCT FROM OLD.summary
                OR NEW.reference_source IS DISTINCT FROM OLD.reference_source
                OR NEW.reference_version IS DISTINCT FROM OLD.reference_version
                OR NEW.approved_by_id IS DISTINCT FROM OLD.approved_by_id
                OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
            THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Conteúdo de referência de interação aprovada é imutável.';
            END IF;

            RETURN NEW;
        END;
        $function$;
        """
    )
    schema_editor.execute(
        f"""
        CREATE TRIGGER {quote(INTERACTION_TRIGGER)}
        BEFORE UPDATE OR DELETE ON {interaction_table}
        FOR EACH ROW
        EXECUTE FUNCTION {interaction_function}();
        """
    )

    schema_editor.execute(
        f"""
        CREATE OR REPLACE FUNCTION {dose_rule_function}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF OLD.approved_at IS NULL THEN
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END IF;

            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Regra de dose aprovada não pode ser excluída.';
            END IF;

            IF OLD.active = FALSE AND NEW.active = TRUE THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Regra de dose aprovada e desativada exige nova versão.';
            END IF;

            IF NEW.drug_id IS DISTINCT FROM OLD.drug_id
                OR NEW.rule_code IS DISTINCT FROM OLD.rule_code
                OR NEW.basis IS DISTINCT FROM OLD.basis
                OR NEW.min_age_days IS DISTINCT FROM OLD.min_age_days
                OR NEW.max_age_days IS DISTINCT FROM OLD.max_age_days
                OR NEW.min_weight_kg IS DISTINCT FROM OLD.min_weight_kg
                OR NEW.max_weight_kg IS DISTINCT FROM OLD.max_weight_kg
                OR NEW.min_dose IS DISTINCT FROM OLD.min_dose
                OR NEW.max_dose IS DISTINCT FROM OLD.max_dose
                OR NEW.dose_unit IS DISTINCT FROM OLD.dose_unit
                OR NEW.per_kg IS DISTINCT FROM OLD.per_kg
                OR NEW.reference_source IS DISTINCT FROM OLD.reference_source
                OR NEW.reference_version IS DISTINCT FROM OLD.reference_version
                OR NEW.approved_by_id IS DISTINCT FROM OLD.approved_by_id
                OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
            THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Conteúdo de regra de dose aprovada é imutável.';
            END IF;

            RETURN NEW;
        END;
        $function$;
        """
    )
    schema_editor.execute(
        f"""
        CREATE TRIGGER {quote(DOSE_RULE_TRIGGER)}
        BEFORE UPDATE OR DELETE ON {dose_rule_table}
        FOR EACH ROW
        EXECUTE FUNCTION {dose_rule_function}();
        """
    )


def drop_reference_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    interaction = apps.get_model("prescription", "Interaction")
    dose_rule = apps.get_model("prescription", "DoseRule")

    schema_editor.execute(
        f"DROP TRIGGER IF EXISTS {quote(INTERACTION_TRIGGER)} "
        f"ON {quote(interaction._meta.db_table)};"
    )
    schema_editor.execute(
        f"DROP TRIGGER IF EXISTS {quote(DOSE_RULE_TRIGGER)} "
        f"ON {quote(dose_rule._meta.db_table)};"
    )
    schema_editor.execute(f"DROP FUNCTION IF EXISTS {quote(INTERACTION_FUNCTION)}();")
    schema_editor.execute(f"DROP FUNCTION IF EXISTS {quote(DOSE_RULE_FUNCTION)}();")


class Migration(migrations.Migration):
    dependencies = [
        ("prescription", "0004_database_mutation_guards"),
    ]

    operations = [
        migrations.RunPython(create_reference_guards, drop_reference_guards),
    ]
