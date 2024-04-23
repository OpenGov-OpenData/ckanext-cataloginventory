import os
import logging
import simplejson as json

log = logging.getLogger(__name__)


def get_export_map_json(map_filename):  # pylint: disable=W0612
    """
    Reading json export map from file
    :param map_filename: str
    :return: obj
    """

    map_path = os.path.join(os.path.dirname(__file__), 'export_map', map_filename)

    if not os.path.isfile(map_path):
        log.warning('Could not find %s ! Please create it. Use samples from same folder', map_path)
        map_path = os.path.join(os.path.dirname(__file__), 'export_map', 'export.map.json')

    with open(map_path, 'r') as export_map_json:
        json_export_map = json.load(export_map_json)

    return json_export_map
