from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    listings_data_path: str = "evals/datasets/listings_small.jsonl"
    trace_output_dir: str = ".traces"
    model_name: str = "claude-haiku-4-5-20251001"


def load_config() -> Config:
    return Config(
        listings_data_path=os.getenv("LISTINGS_DATA_PATH", Config.listings_data_path),
        trace_output_dir=os.getenv("TRACE_OUTPUT_DIR", Config.trace_output_dir),
        model_name=os.getenv("MODEL_NAME", Config.model_name),
    )

