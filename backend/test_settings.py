import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.settings import CONFIG_FILE, load_config
from backend.detection.config import line_config


class SettingsTests(unittest.TestCase):
    def test_paths_are_relative_to_file_not_working_directory(self):
        original = json.loads(CONFIG_FILE.read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'custom.json'
            path.write_text(json.dumps(original))
            config = load_config(path)
            self.assertEqual(config['detection']['model_path'], str(Path(directory) / original['detection']['model_path']))

    def test_shared_loader_and_environment_precedence(self):
        from backend.monitoring.monitor_residuos import load_config as rpi_load
        with patch.dict(os.environ, {'AQUADETECTOR_API_URL': 'http://server:8000', 'BOTTLE_COUNT_API_URL': 'http://other:8000', 'BOTTLE_COUNT_STATION_ID': '9'}):
            self.assertEqual(load_config(), rpi_load())
            self.assertEqual(load_config()['backend']['base_url'], 'http://server:8000')
            self.assertEqual(load_config()['station_id'], 9)

    def test_line_follows_configuration(self):
        config = load_config()
        config['tracking'].update(line_y_ratio=.25, direction='down')
        line = line_config(config, 800, 600)
        self.assertEqual(line.start, (0, 150))
        self.assertEqual(line.end, (800, 150))
        self.assertEqual(line.direction, 'positive')


if __name__ == '__main__':
    unittest.main()
