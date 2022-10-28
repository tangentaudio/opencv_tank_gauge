CREATE TABLE config (
       key TEXT PRIMARY KEY,
       min REAL NOT NULL,
       max REAL not NULL,
       value REAL NOT NULL
);

INSERT INTO config (key, min, max, value)
VALUES ('rotate_angle', -5, 5, 0),
       ('crop_x1', 0, 799, 375),
       ('crop_x2', 0, 799, 405),
       ('crop_y1', 0, 607, 20),
       ('crop_y2', 0, 607, 535),
       ('slice_x1', 0, 799, 458),
       ('slice_x2', 0, 799, 468),
       ('tick_threshold', 0, 255, 60),
       ('tick_blur', 1, 16, 8),
       ('indicator_blur', 1, 16, 2),
       ('indicator_threshold', 0, 255, 20),
       ('level_average_points', 1, 30, 30),
       ('level_max_deviation', 1, 10, 3.0);
       
