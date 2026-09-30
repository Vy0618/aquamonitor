"""Shared JSON configuration; paths are relative to the configuration file."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

CONFIG_FILE = Path(os.getenv('AQUAMONITOR_CONFIG', Path(__file__).resolve().parents[1] / 'aquamonitor.json'))


def load_config(path=None):
    path = Path(path or CONFIG_FILE).resolve()
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(config, dict):
        raise ValueError('Configuration must be a JSON object')
    display = config.setdefault('display', {'enabled': True})
    processing = config.setdefault('image_processing', {'enabled': False, 'max_width': 640, 'max_height': 480})
    for name, section in (('display', display), ('image_processing', processing)):
        if not isinstance(section, dict) or type(section.get('enabled')) is not bool:
            raise ValueError(f'{name}.enabled must be a boolean')
    for key in ('max_width', 'max_height'):
        if type(processing.get(key)) is not int or processing[key] <= 0:
            raise ValueError(f'image_processing.{key} must be a positive integer')
    backend = config['backend']
    backend['base_url'] = os.getenv('AQUADETECTOR_API_URL', os.getenv('BOTTLE_COUNT_API_URL', backend['base_url'])).rstrip('/')
    config['station_id'] = int(os.environ['BOTTLE_COUNT_STATION_ID']) if 'BOTTLE_COUNT_STATION_ID' in os.environ else config['station_id']
    if 'BOTTLE_COUNT_API_ENABLED' in os.environ:
        backend['enabled'] = os.environ['BOTTLE_COUNT_API_ENABLED'] == '1'
    if 'BOTTLE_COUNT_PUBLISH_INTERVAL' in os.environ:
        backend['publish_interval_seconds'] = float(os.environ['BOTTLE_COUNT_PUBLISH_INTERVAL'])
    if type(config['station_id']) is not int or config['station_id'] <= 0:
        raise ValueError('station_id must be a positive integer')
    url = urlparse(backend['base_url'])
    if url.scheme not in ('http', 'https') or not url.hostname:
        raise ValueError('backend.base_url must be an HTTP URL')
    for value in (config['detection_interval_ms'], backend['timeout_seconds'], backend['publish_interval_seconds'], *[config['camera'][k] for k in ('width','height','fps')]):
        if type(value) not in (int, float) or not 0 < value < float('inf'):
            raise ValueError('Intervals, resolution and FPS must be positive and finite')
    if not 0 < config['tracking']['line_y_ratio'] < 1:
        raise ValueError('tracking.line_y_ratio must be between 0 and 1')
    if config['tracking']['direction'] not in ('up','down','both'):
        raise ValueError('Invalid tracking direction')
    for section, fields in (('station_document', ('path',)), ('detection', ('model_path',)), ('ssd_mobilenet', ('model_path','config_path','labels_path'))):
        for field in fields:
            config[section][field] = str((path.parent / config[section][field]).resolve())
    return config
