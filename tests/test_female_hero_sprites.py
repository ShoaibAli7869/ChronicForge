import importlib.util, pathlib, sys

def _load():
    spec = importlib.util.spec_from_file_location(
        'gen', pathlib.Path('tools/generate_female_hero.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_palette_constants():
    mod = _load()
    for key in ('hair', 'skin', 'eye', 'jacket', 'pants', 'boot', 'scarf', 'outline'):
        assert key in mod.C, f"missing palette key: {key}"

def test_new_frame_size():
    mod = _load()
    img = mod.new_frame()
    assert img.size == (128, 128)
    assert img.mode == 'RGBA'

def test_make_strip_width():
    mod = _load()
    frames = [mod.new_frame() for _ in range(5)]
    strip = mod.make_strip(frames)
    assert strip.size == (640, 128)
