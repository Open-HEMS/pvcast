from pathlib import Path

LOC_EUW = (52.3585, 4.8810, 0.0)
LOC_USW = (40.6893, -74.0445, 0.0)
LOC_AUS = (-31.9741, 115.8517, 0.0)

TEST_CONF_PATH_SEC = Path(__file__).parent.parent / "tests" / "test_config_sec.yaml"
TEST_CONF_PATH_NO_SEC = Path(__file__).parent.parent / "tests" / "test_config_no_sec.yaml"
TEST_CONF_PATH_ERROR = Path(__file__).parent.parent / "tests" / "test_config_error.yaml"
TEST_SECRETS_PATH = Path(__file__).parent.parent / "tests" / "test_secrets.yaml"
