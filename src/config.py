from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    listings_csv_path: str | None = None
    h2c_base_url: str = "https://homestocompare.com"
    h2c_read_key: str | None = None
    h2c_visitor_session: str | None = None
    trace_output_dir: str = ".traces"
    model_name: str = "claude-haiku-4-5-20251001"


def load_config() -> Config:
    return Config(
        listings_csv_path=os.getenv("LISTINGS_CSV_PATH") or None,
        h2c_base_url=os.getenv("H2C_BASE_URL", Config.h2c_base_url),
        h2c_read_key=os.getenv("H2C_READ_KEY") or None,
        h2c_visitor_session=os.getenv("H2C_VISITOR_SESSION") or None,
        trace_output_dir=os.getenv("TRACE_OUTPUT_DIR", Config.trace_output_dir),
        model_name=os.getenv("MODEL_NAME", Config.model_name),
    )
