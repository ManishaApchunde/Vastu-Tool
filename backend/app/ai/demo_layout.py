"""Reference layout used by the demo floor plan image and the mock analyzer.
Coordinates are on a 1000 x 800 canvas; the plan's top edge is drawn as North in the demo."""

CANVAS = (1000, 800)
BOUNDARY = [[100, 100], [900, 100], [900, 700], [100, 700]]

# (id, label drawn on the image, room_type, polygon)
ROOMS = [
    ("r_toilet1", "Toilet", "toilet", [[100, 100], [260, 100], [260, 230], [100, 230]]),
    ("r_living", "Living Room", "living", [[260, 100], [700, 100], [700, 330], [260, 330]]),
    ("r_pooja", "Pooja", "pooja", [[700, 100], [900, 100], [900, 220], [700, 220]]),
    ("r_bed2", "Bedroom 2", "bedroom", [[100, 230], [260, 230], [260, 470], [100, 470]]),
    ("r_toilet2", "Bath", "toilet", [[400, 330], [540, 330], [540, 470], [400, 470]]),
    ("r_stairs", "Stairs", "staircase", [[700, 220], [900, 220], [900, 470], [700, 470]]),
    ("r_master", "Master Bedroom", "master_bedroom", [[100, 470], [400, 470], [400, 700], [100, 700]]),
    ("r_dining", "Dining", "dining", [[400, 470], [650, 470], [650, 700], [400, 700]]),
    ("r_kitchen", "Kitchen", "kitchen", [[650, 470], [900, 470], [900, 700], [650, 700]]),
]

DOORS = [  # (id, position, is_main_entrance)
    ("d_main", [560, 100], True),
    ("d_bed2", [260, 380], False),
    ("d_bath", [470, 330], False),
    ("d_master", [300, 470], False),
    ("d_kitchen", [700, 560], False),
    ("d_toilet1", [180, 230], False),
]

WINDOWS = [
    ("w_living", [420, 100]),
    ("w_pooja", [900, 160]),
    ("w_kitchen", [900, 600]),
    ("w_master", [250, 700]),
    ("w_bed2", [100, 350]),
]
