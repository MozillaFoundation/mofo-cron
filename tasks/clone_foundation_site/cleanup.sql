CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION clean_user_data()
RETURNS VOID AS $$
DECLARE
    user_row RECORD;
    new_email varchar;
    new_hash varchar;
    new_username varchar;
    counter integer := 1;
BEGIN
--     scrub the user table
    TRUNCATE django_session;

--     scrub non-staff social auth data
    TRUNCATE social_auth_usersocialauth;

--     Update the site domain
    UPDATE django_site
    SET domain = 'foundation.mofostaging.net'
    WHERE domain = 'foundation.mozilla.org';

--     Iterate over each non-staff user and remove any PII
    FOR user_row IN
        SELECT id
        FROM auth_user
        WHERE email NOT LIKE '%@mozillafoundation.org'
    LOOP
        new_email := concat(encode(gen_random_bytes(12), 'base64'), '@example.com');
        new_hash := crypt(encode(gen_random_bytes(32), 'base64'), gen_salt('bf', 6));
        new_username := concat('anonymouse', counter::varchar);

        UPDATE auth_user
        SET
          email = new_email,
          password = new_hash,
          username = new_username,
          first_name = 'anony',
          last_name = 'mouse'
        Where id = user_row.id;

--         Increase the counter
        counter := counter + 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

SELECT clean_user_data();


