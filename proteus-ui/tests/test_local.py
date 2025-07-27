import toml
import yaml
import unittest


class Tests(unittest.TestCase):
    def test_toml(self):
        filename = "data/test_config.toml"
        with open(filename, encoding="utf-8-sig") as input:
            file_contents = input.read()
        parsed = toml.loads(file_contents)

        assert parsed['theme']['base'] == 'light'
        assert parsed['theme']['primaryColor'] == '#F63366'
        assert parsed['theme']['secondaryBackgroundColor'] == '#FFFFFF'

    def test_yaml(self):
        config_file = "data/test_config.yml"
        with open(config_file, "r", encoding="utf-8") as file:
            c = yaml.safe_load(file)
        assert c['theme']['base'] == 'light'
        assert c['theme']['primaryColor'] == '#F63366'
        assert c['theme']['secondaryBackgroundColor'] == '#FFFFFF'
