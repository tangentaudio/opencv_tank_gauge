CREATE TABLE config (
       key TEXT PRIMARY KEY,
       min REAL NOT NULL,
       max REAL not NULL,
       value REAL NOT NULL
);

INSERT INTO config (key, min, max, value)
VALUES ('rotate_angle', -5, 5, 0),
       ('crop_x1', 0, 800, 332),
       ('crop_x2', 0, 800, 475),
       ('crop_y1', 0, 608, 18),
       ('crop_y2', 0, 608, 536),
       ('slice_x1', 0, 800, 500),
       ('slice_x2', 0, 800, 520),       
       ('tick_threshold', 0, 255, 58);
       
