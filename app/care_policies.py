"""PostgreSQL defense in depth for a non-owner runtime role, not a client DB API."""

import re


def install(connection, schema=None):
    if connection.dialect.name != "postgresql":
        return
    schema = schema or connection.exec_driver_sql("SELECT current_schema()").scalar()
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", schema):
        raise ValueError("Invalid schema")
    s = '"' + schema + '"'
    actor = "nullif(current_setting('neurotwin.actor_id',true),'')"
    connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION {s}.care_allowed(p text,a text,b text) RETURNS boolean LANGUAGE sql STABLE AS $$
        SELECT {actor} IN (a,b) AND EXISTS (
          SELECT 1 FROM {s}.patients p1 JOIN {s}.users u1 ON u1.id=a JOIN {s}.users u2 ON u2.id=b
          JOIN {s}.grants g1 ON g1.user_id=a AND g1.patient_id=p1.id
          JOIN {s}.grants g2 ON g2.user_id=b AND g2.patient_id=p1.id
          WHERE p1.id=p AND p1.org=u1.org AND p1.org=u2.org AND a<>b
          AND u1.role IN ('participant','family','clinician') AND u2.role IN ('participant','family','clinician')
          AND g1.active AND g2.active AND g1.scopes::jsonb ? 'messages' AND g2.scopes::jsonb ? 'messages')
        $$""")
    convo = f"EXISTS (SELECT 1 FROM {s}.care_conversations c WHERE c.id=conversation_id AND {s}.care_allowed(c.patient_id,c.first_user,c.second_user))"
    msg = f"EXISTS (SELECT 1 FROM {s}.care_messages m WHERE m.id=message_id AND {s}.care_allowed(m.patient_id,m.sender_id,m.recipient_id))"
    matching = f"(conversation_id IS NULL OR EXISTS (SELECT 1 FROM {s}.care_conversations c WHERE c.id=care_messages.conversation_id AND c.patient_id=care_messages.patient_id AND c.first_user=least(care_messages.sender_id,care_messages.recipient_id) AND c.second_user=greatest(care_messages.sender_id,care_messages.recipient_id)))"
    message = f"{s}.care_allowed(patient_id,sender_id,recipient_id) AND {matching}"
    policies = {
        "care_conversations": (
            f"{s}.care_allowed(patient_id,first_user,second_user)",
            f"{s}.care_allowed(patient_id,first_user,second_user) AND created_by={actor}",
        ),
        "care_participants": (convo, convo),
        "care_messages": (message, f"{message} AND sender_id={actor}"),
        "care_attachments": (
            f"{convo} AND (uploader_id={actor} OR (status='committed' AND {msg}))",
            f"{convo} AND uploader_id={actor}",
        ),
        "care_receipts": (
            msg,
            f"recipient_id={actor} AND EXISTS (SELECT 1 FROM {s}.care_messages m WHERE m.id=message_id AND m.recipient_id={actor} AND {s}.care_allowed(m.patient_id,m.sender_id,m.recipient_id))",
        ),
        "care_events": (convo, convo),
        "care_audio": (msg, msg),
    }
    for table, (read, insert) in policies.items():
        connection.exec_driver_sql(
            f'ALTER TABLE {s}."{table}" ENABLE ROW LEVEL SECURITY'
        )
        for command, expression in [
            ("SELECT", read),
            ("INSERT", insert),
            (
                "UPDATE",
                read if table in {"care_messages", "care_conversations"} else insert,
            ),
            ("DELETE", "false"),
        ]:
            name = "care_" + command.lower()
            connection.exec_driver_sql(
                f'DROP POLICY IF EXISTS "{name}" ON {s}."{table}"'
            )
            if table == "care_events" and command == "UPDATE":
                expression = "false"
            clause = (
                f"WITH CHECK ({expression})"
                if command == "INSERT"
                else f"USING ({expression}) WITH CHECK ({expression})"
                if command == "UPDATE"
                else f"USING ({expression})"
            )
            connection.exec_driver_sql(
                f'CREATE POLICY "{name}" ON {s}."{table}" FOR {command} {clause}'
            )
    connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION {s}.care_message_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE actor text := {actor};
      BEGIN
        IF actor IS NULL THEN RETURN NEW; END IF;
        IF ROW(NEW.patient_id,NEW.sender_id,NEW.recipient_id,NEW.command_id,NEW.body,NEW.media::text,NEW.reply_to_id,NEW.created_at)
            IS DISTINCT FROM ROW(OLD.patient_id,OLD.sender_id,OLD.recipient_id,OLD.command_id,OLD.body,OLD.media::text,OLD.reply_to_id,OLD.created_at)
            OR (OLD.conversation_id IS NOT NULL AND NEW.conversation_id IS DISTINCT FROM OLD.conversation_id)
            OR (NEW.opened_at IS DISTINCT FROM OLD.opened_at AND actor<>OLD.recipient_id)
            OR (NEW.withdrawn_at IS DISTINCT FROM OLD.withdrawn_at AND actor<>OLD.sender_id)
        THEN RAISE EXCEPTION 'immutable care message'; END IF;
        RETURN NEW;
      END $$""")
    connection.exec_driver_sql(
        f"DROP TRIGGER IF EXISTS care_message_immutable ON {s}.care_messages"
    )
    connection.exec_driver_sql(
        f"CREATE TRIGGER care_message_immutable BEFORE UPDATE ON {s}.care_messages FOR EACH ROW EXECUTE FUNCTION {s}.care_message_immutable()"
    )
