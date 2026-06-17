from tokenforge_local.models import Preferences
from tokenforge_local.preferences import load_preferences, save_preferences


def test_preference_loading_saving(tmp_path):
    path = tmp_path / "prefs.json"
    prefs = Preferences()
    prefs.printer.nozzle_size_mm = 0.6
    prefs.palette[0].enabled = False
    save_preferences(prefs, path)

    loaded = load_preferences(path)
    assert loaded.printer.nozzle_size_mm == 0.6
    assert loaded.palette[0].enabled is False
