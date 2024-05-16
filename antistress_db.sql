CREATE TABLE stress_predictions (
    stress_prediction_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    worker_id smallint NOT NULL,
    stress_level varchar(100) NOT NULL CHECK (
        stress_level IN (
            'Низкий уровень стресса',
            'Средний уровень стресса',
            'Высокий уровень стресса'
        )
    ),
    prediction_date timestamp NOT NULL
);
CREATE TABLE workers (
    worker_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name varchar(100) NOT NULL,
    last_name varchar(100) NOT NULL,
    surname varchar(100) NOT NULL,
    mental_health_history boolean NOT NULL,
    UNIQUE (first_name, last_name, surname)
);
CREATE TABLE workers_info (
    worker_info_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    worker_id smallint NOT NULL,
    info_date timestamp NOT NULL,
    anxiety smallint NOT NULL CHECK (
        anxiety BETWEEN 0 AND 21
    ),
    self_esteem smallint NOT NULL CHECK (
        self_esteem BETWEEN 0 AND 30
    ),
    depression smallint NOT NULL CHECK (
        depression BETWEEN 0 AND 27
    ),
    headache smallint NOT NULL CHECK (
        headache BETWEEN 0 AND 5
    ),
    blood_pressure smallint NOT NULL CHECK (
        blood_pressure BETWEEN 1 AND 3
    ),
    sleep_quality smallint NOT NULL CHECK (
        sleep_quality BETWEEN 0 AND 5
    ),
    breathing_problem smallint NOT NULL CHECK (
        breathing_problem BETWEEN 0 AND 5
    ),
    noise_level smallint NOT NULL CHECK (
        noise_level BETWEEN 0 AND 5
    ),
    social_support smallint NOT NULL CHECK (
        social_support BETWEEN 0 AND 3
    ),
    extracurricular_activities smallint NOT NULL CHECK (
        extracurricular_activities BETWEEN 0 AND 5
    )
);
ALTER TABLE stress_predictions
ADD CONSTRAINT fk_worker1 FOREIGN KEY (worker_id) REFERENCES workers (worker_id) ON DELETE CASCADE;
ALTER TABLE workers_info
ADD CONSTRAINT fk_worker2 FOREIGN KEY (worker_id) REFERENCES workers (worker_id) ON DELETE CASCADE;
CREATE PROCEDURE add_worker(
    f_name varchar,
    l_name varchar,
    s_name varchar,
    m_history boolean
) LANGUAGE SQL AS $$
INSERT INTO workers (
        first_name,
        last_name,
        surname,
        mental_health_history
    )
VALUES (f_name, l_name, s_name, m_history);
$$;
CREATE PROCEDURE delete_worker(f_name varchar, l_name varchar, s_name varchar) LANGUAGE SQL AS $$
DELETE FROM workers
WHERE first_name = f_name
    AND last_name = l_name
    AND surname = s_name;
$$;
CREATE PROCEDURE save_features(
    f_name varchar,
    l_name varchar,
    s_name varchar,
    info_date timestamp,
    anxiety integer,
    self_esteem integer,
    depression integer,
    headache integer,
    blood_pressure integer,
    sleep_quality integer,
    breathing_problem integer,
    noise_level integer,
    social_support integer,
    extracurricular_activities integer
) LANGUAGE SQL AS $$
INSERT INTO workers_info(
        worker_id,
        info_date,
        anxiety,
        self_esteem,
        depression,
        headache,
        blood_pressure,
        sleep_quality,
        breathing_problem,
        noise_level,
        social_support,
        extracurricular_activities
    )
VALUES (
        (
            SELECT worker_id
            FROM workers
            WHERE first_name = f_name
                AND last_name = l_name
                AND surname = s_name
        ),
        info_date,
        anxiety,
        self_esteem,
        depression,
        headache,
        blood_pressure,
        sleep_quality,
        breathing_problem,
        noise_level,
        social_support,
        extracurricular_activities
    );
$$;
CREATE PROCEDURE save_prediction(
    f_name varchar,
    l_name varchar,
    s_name varchar,
    stress_level varchar
) LANGUAGE SQL AS $$
INSERT INTO stress_predictions(worker_id, stress_level, prediction_date)
VALUES (
        (
            SELECT worker_id
            FROM workers
            WHERE first_name = f_name
                AND last_name = l_name
                AND surname = s_name
        ),
        stress_level,
        CURRENT_TIMESTAMP
    );
$$;